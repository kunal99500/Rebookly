"""Business photos: upload, replace, reorder, delete.

Upload order matters:
  1. the owner must confirm the photo is real,
  2. the ORIGINAL file is checked for AI-generation labels (before metadata is stripped),
  3. the image is processed (rotated, resized, metadata removed) and stored.
"""
import asyncio
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import get_clock
from app.media.authenticity import check_provenance
from app.media.processing import ImageError, prepare_image
from app.media.schemas import PhotoOut, PhotoUpdate
from app.media.storage import StorageError, SupabaseStorage
from app.models import Business, BusinessPhoto, Service
from app.services import audit

PHOTO_BUCKET = "business-photos"
MAX_GALLERY_PHOTOS = 8


def to_out(storage: SupabaseStorage, photo: BusinessPhoto) -> PhotoOut:
    return PhotoOut(
        id=photo.id, kind=photo.kind, service_id=photo.service_id,
        url=storage.public_url(PHOTO_BUCKET, photo.storage_path),
        thumb_url=storage.public_url(PHOTO_BUCKET, photo.thumb_path),
        width=photo.width, height=photo.height, alt_text=photo.alt_text, sort_order=photo.sort_order,
        moderation_status=photo.moderation_status,
    )


async def list_photos(session: AsyncSession, business_id: uuid.UUID, public_only: bool = False) -> list[BusinessPhoto]:
    query = select(BusinessPhoto).where(BusinessPhoto.business_id == business_id)
    if public_only:
        query = query.where(BusinessPhoto.moderation_status == "approved")
    result = await session.scalars(
        query.order_by(BusinessPhoto.kind, BusinessPhoto.sort_order, BusinessPhoto.created_at)
    )
    return list(result)


async def upload_photo(
    session: AsyncSession, storage: SupabaseStorage, business: Business, owner_id: uuid.UUID,
    data: bytes, kind: str, service_id: uuid.UUID | None, alt_text: str | None, confirmed_real: bool,
) -> BusinessPhoto:
    # 1. The owner must confirm the photo is real.
    if not confirmed_real:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Please confirm this is a real, unaltered photo of your business")

    # 2. Check what kind of photo this is and whether there's room for it.
    replacing: BusinessPhoto | None = None
    if kind == "service":
        if service_id is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Choose which service this photo is for")
        service = await session.scalar(select(Service).where(Service.id == service_id,
                                                             Service.business_id == business.id))
        if service is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Service not found")
        replacing = await session.scalar(select(BusinessPhoto).where(
            BusinessPhoto.service_id == service_id, BusinessPhoto.kind == "service"))
    else:
        service_id = None
        if kind == "cover":
            replacing = await session.scalar(select(BusinessPhoto).where(
                BusinessPhoto.business_id == business.id, BusinessPhoto.kind == "cover"))
        else:
            count = await session.scalar(select(func.count()).select_from(BusinessPhoto).where(
                BusinessPhoto.business_id == business.id, BusinessPhoto.kind == "gallery"))
            if count >= MAX_GALLERY_PHOTOS:
                raise HTTPException(status.HTTP_409_CONFLICT,
                                    f"You can have up to {MAX_GALLERY_PHOTOS} gallery photos. Delete one first.")

    # 3. Reject AI-generated or AI-edited images, using the ORIGINAL file's provenance information.
    provenance = await asyncio.to_thread(check_provenance, data)
    if provenance.ai_generated:
        audit.record(session, actor_type="owner", actor_id=owner_id, action="photo.rejected_ai",
                     business_id=business.id, details={"reasons": provenance.reasons, "kind": kind})
        await session.commit()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "This looks like an AI-generated or AI-edited image. "
                            "Rebookly only accepts real photos of your business.")

    # 4. Check and prepare the image (CPU work, so it runs off the main thread).
    try:
        prepared = await asyncio.to_thread(prepare_image, data)
    except ImageError as err:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(err))

    # 5. Upload both sizes to Storage.
    photo_id = uuid.uuid4()
    path, thumb = f"{business.id}/{photo_id}.webp", f"{business.id}/{photo_id}_thumb.webp"
    try:
        await storage.upload(PHOTO_BUCKET, path, prepared.large, "image/webp")
        await storage.upload(PHOTO_BUCKET, thumb, prepared.thumb, "image/webp")
    except StorageError:
        await _quiet_delete(storage, [path, thumb])
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Couldn't save the photo right now. Please try again.")

    # 6. Save the record (replacing an old cover or service photo in the same transaction).
    old_files = []
    if replacing is not None:
        old_files = [replacing.storage_path, replacing.thumb_path]
        await session.delete(replacing)
        await session.flush()  # remove the old row first, so the "one cover" rule isn't broken
    next_order = (await session.scalar(select(func.coalesce(func.max(BusinessPhoto.sort_order), -1)).where(
        BusinessPhoto.business_id == business.id, BusinessPhoto.kind == kind))) + 1
    photo = BusinessPhoto(
        id=photo_id, business_id=business.id, service_id=service_id, kind=kind,
        storage_path=path, thumb_path=thumb, width=prepared.width, height=prepared.height,
        alt_text=alt_text, sort_order=next_order,
        attested_real_at=get_clock().now(), moderation_status="approved",
    )
    session.add(photo)
    audit.record(session, actor_type="owner", actor_id=owner_id, action="photo.uploaded",
                 business_id=business.id, details={"photo_id": str(photo_id), "kind": kind, "attested_real": True})
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        await _quiet_delete(storage, [path, thumb])
        raise
    await _quiet_delete(storage, old_files)
    await session.refresh(photo)
    return photo


async def update_photo(session: AsyncSession, photo: BusinessPhoto, owner_id: uuid.UUID, data: PhotoUpdate) -> BusinessPhoto:
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(photo, field, value)
    if changes:
        audit.record(session, actor_type="owner", actor_id=owner_id, action="photo.updated",
                     business_id=photo.business_id, details={"photo_id": str(photo.id), "fields": sorted(changes)})
        await session.commit()
        await session.refresh(photo)
    return photo


async def delete_photo(session: AsyncSession, storage: SupabaseStorage, photo: BusinessPhoto, owner_id: uuid.UUID) -> None:
    files = [photo.storage_path, photo.thumb_path]
    await session.delete(photo)
    audit.record(session, actor_type="owner", actor_id=owner_id, action="photo.deleted",
                 business_id=photo.business_id, details={"photo_id": str(photo.id), "kind": photo.kind})
    await session.commit()
    await _quiet_delete(storage, files)


async def _quiet_delete(storage: SupabaseStorage, paths: list[str]) -> None:
    """Best-effort clean-up of files; a leftover file is harmless, a crash here isn't."""
    try:
        await storage.delete(PHOTO_BUCKET, paths)
    except StorageError:
        pass