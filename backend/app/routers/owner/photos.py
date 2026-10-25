"""Owner API: business photos."""
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.supabase_auth import AuthUser
from app.db import get_session
from app.media import photos
from app.media.processing import MAX_UPLOAD_BYTES
from app.media.schemas import PhotoOut, PhotoUpdate
from app.models import Business, BusinessPhoto
from app.routers.owner.deps import get_owned_business, get_owner

router = APIRouter(prefix="/api/owner/businesses/{business_id}/photos", tags=["owner: photos"])


def _storage(request: Request):
    storage = getattr(request.app.state, "storage", None)
    if storage is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Photo storage is not configured")
    return storage


async def get_owned_photo(
    photo_id: uuid.UUID,
    business: Business = Depends(get_owned_business),
    session: AsyncSession = Depends(get_session),
) -> BusinessPhoto:
    photo = await session.scalar(select(BusinessPhoto).where(
        BusinessPhoto.id == photo_id, BusinessPhoto.business_id == business.id))
    if photo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Photo not found")
    return photo


@router.post("", response_model=PhotoOut, status_code=status.HTTP_201_CREATED)
async def upload(
    request: Request,
    file: UploadFile = File(description="JPEG, PNG or WebP, up to 5 MB"),
    kind: Literal["cover", "gallery", "service"] = Form("gallery"),
    service_id: uuid.UUID | None = Form(None),
    alt_text: str | None = Form(None, max_length=200),
    confirm_real_photo: bool = Form(
        False, description="Required: I confirm this is a real, unaltered photo of my business (not AI-generated)"
    ),
    business: Business = Depends(get_owned_business),
    owner: AuthUser = Depends(get_owner),
    session: AsyncSession = Depends(get_session),
):
    """Upload a real photo. AI-generated or AI-edited images are rejected.

    A new cover (or service photo) replaces the previous one.
    """
    storage = _storage(request)
    data = await file.read(MAX_UPLOAD_BYTES + 1)  # read at most a little over the limit
    photo = await photos.upload_photo(
        session, storage, business, owner.id, data, kind, service_id, alt_text, confirm_real_photo
    )
    return photos.to_out(storage, photo)


@router.get("", response_model=list[PhotoOut])
async def list_all(request: Request, business: Business = Depends(get_owned_business),
                   session: AsyncSession = Depends(get_session)):
    storage = _storage(request)
    return [photos.to_out(storage, p) for p in await photos.list_photos(session, business.id)]


@router.patch("/{photo_id}", response_model=PhotoOut)
async def update(
    data: PhotoUpdate, request: Request,
    photo: BusinessPhoto = Depends(get_owned_photo),
    owner: AuthUser = Depends(get_owner),
    session: AsyncSession = Depends(get_session),
):
    """Change the description (alt text) or the order in the gallery."""
    return photos.to_out(_storage(request), await photos.update_photo(session, photo, owner.id, data))


@router.delete("/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    request: Request,
    photo: BusinessPhoto = Depends(get_owned_photo),
    owner: AuthUser = Depends(get_owner),
    session: AsyncSession = Depends(get_session),
):
    await photos.delete_photo(session, _storage(request), photo, owner.id)