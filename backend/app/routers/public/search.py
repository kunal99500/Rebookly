"""Public API: find businesses by what the client types and where they are."""
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.media import photos
from app.rules.catalog import CATEGORIES
from app.schemas.search import SearchOut
from app.services import search as search_service

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/search", response_model=SearchOut)
async def search(
    request: Request,
    q: str = Query(default="", max_length=100, description='What the client typed, e.g. "barber shop near me"'),
    lat: float | None = Query(default=None, ge=-90, le=90, description="Client's location (used once, never stored)"),
    lng: float | None = Query(default=None, ge=-180, le=180),
    radius_km: float = Query(default=10, gt=0, le=50),
    category: Literal[CATEGORIES] | None = Query(default=None),  # type: ignore[valid-type]
    session: AsyncSession = Depends(get_session),
):
    """Live, publicly listed businesses that match. Nearest first when a location is given, otherwise best rated."""
    storage = getattr(request.app.state, "storage", None)
    photo_url = (lambda path: storage.public_url(photos.PHOTO_BUCKET, path)) if storage else None
    return await search_service.search(session, q, lat if lng is not None else None,
                                       lng if lat is not None else None, radius_km, category, photo_url)