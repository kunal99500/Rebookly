"""Client API: delete my data."""
import logging
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.admin import AuthAdminError, delete_auth_user
from app.auth.dependencies import get_current_user
from app.auth.supabase_auth import AuthUser
from app.config import get_settings
from app.db import get_session
from app.services import account_deletion, clients

logger = logging.getLogger("rebookly.account")
router = APIRouter(prefix="/api/client/account", tags=["client: account"])


class DeletionCheck(BaseModel):
    can_delete: bool
    reasons: list[str]
    what_happens: str = ("Your name, phone number, email, reviews and waitlist entries are deleted, and your "
                         "sign-in account is removed. Businesses keep the booking and payment records the law "
                         "requires, and receipts already issued stay as they were, because they're financial records.")


class DeleteConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: Literal["DELETE"]


@router.get("/deletion-check", response_model=DeletionCheck)
async def deletion_check(user: AuthUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    """Can my data be deleted right now, and what exactly happens?"""
    reasons = await account_deletion.blockers(session, await clients.require_client(session, user))
    return DeletionCheck(can_delete=not reasons, reasons=reasons)


@router.post("/delete")
async def delete_my_data(data: DeleteConfirm, user: AuthUser = Depends(get_current_user),
                         session: AsyncSession = Depends(get_session)):
    """Delete my personal data and my sign-in account. Send {"confirm": "DELETE"}. This can't be undone."""
    client = await clients.require_client(session, user)
    auth_user_id = await account_deletion.delete_client_data(session, client)
    settings = get_settings()
    if auth_user_id and settings.supabase_url and settings.supabase_service_role_key.get_secret_value():
        try:
            await delete_auth_user(settings.supabase_url, settings.supabase_service_role_key.get_secret_value(),
                                   auth_user_id)
        except (AuthAdminError, Exception):
            # The personal data is already gone; the leftover sign-in account holds only the phone number.
            logger.exception("Couldn't remove sign-in account %s; remove it in the Supabase dashboard", auth_user_id)
    return {"deleted": True}