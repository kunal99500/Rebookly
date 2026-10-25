"""Owner API: the services a business sells."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.supabase_auth import AuthUser
from app.db import get_session
from app.models import Business, Service
from app.routers.owner.deps import get_owned_business, get_owner
from app.schemas.service import ServiceCreate, ServiceOut, ServiceUpdate
from app.services import offerings

router = APIRouter(prefix="/api/owner/businesses/{business_id}/services", tags=["owner: services"])


async def get_owned_service(
    service_id: uuid.UUID,
    business: Business = Depends(get_owned_business),
    session: AsyncSession = Depends(get_session),
) -> Service:
    """A service, only if it belongs to a business the signed-in owner owns."""
    service = await session.scalar(
        select(Service).where(Service.id == service_id, Service.business_id == business.id)
    )
    if service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service not found")
    return service


@router.post("", response_model=ServiceOut, status_code=status.HTTP_201_CREATED)
async def create_service(
    data: ServiceCreate,
    business: Business = Depends(get_owned_business),
    owner: AuthUser = Depends(get_owner),
    session: AsyncSession = Depends(get_session),
):
    return await offerings.create_service(session, business, owner.id, data)


@router.get("", response_model=list[ServiceOut])
async def list_services(business: Business = Depends(get_owned_business), session: AsyncSession = Depends(get_session)):
    return await offerings.list_services(session, business)


@router.patch("/{service_id}", response_model=ServiceOut)
async def update_service(
    data: ServiceUpdate,
    service: Service = Depends(get_owned_service),
    owner: AuthUser = Depends(get_owner),
    session: AsyncSession = Depends(get_session),
):
    """Change some fields. To stop offering a service, set is_active to false (it's never deleted)."""
    return await offerings.update_service(session, service, owner.id, data)