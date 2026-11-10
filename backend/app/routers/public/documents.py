"""Public document pages. The long random token in the link is the only key, so links are shared with care."""
from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.documents.render import render_document
from app.models import Document

router = APIRouter(tags=["documents"])


@router.get("/documents/{token}", response_class=HTMLResponse, include_in_schema=False)
async def show_document(
    token: str = Path(min_length=30, max_length=100),
    session: AsyncSession = Depends(get_session),
):
    document = await session.scalar(select(Document).where(Document.access_token == token))
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    html = render_document(document, get_settings().frontend_url)
    # private: browsers may keep a copy, but shared caches (e.g. proxies) must not.
    return HTMLResponse(html, headers={"Cache-Control": "private, max-age=300", "X-Robots-Tag": "noindex"})