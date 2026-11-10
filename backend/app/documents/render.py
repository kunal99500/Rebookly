"""Turns a saved document into a web page (which also prints cleanly as a PDF from the browser)."""
from pathlib import Path

import segno
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from app.models import Document

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
_env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=select_autoescape(["html"]))


def qr_svg(text: str) -> Markup:
    """The check-in QR code as inline SVG: no image files, works offline and in print."""
    svg = segno.make_qr(text, error="m").svg_inline(scale=5, border=2, dark="#161B2E", light="#FFFFFF")
    return Markup(svg)


def render_document(document: Document, frontend_url: str) -> str:
    snapshot = document.snapshot
    template = _env.get_template(f"documents/{document.type}.html")
    token = snapshot.get("check_in_token")
    return template.render(doc=snapshot, qr=qr_svg(token) if token else None, frontend_url=frontend_url)