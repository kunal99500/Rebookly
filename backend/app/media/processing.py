"""Checks and prepares uploaded photos. Pure functions: no storage, no database.

Every upload is opened and re-encoded, which:
  * proves it's a real image (not a renamed file),
  * fixes phone-camera rotation,
  * removes ALL hidden metadata, including GPS location,
  * creates a large version and a small thumbnail as compact WebP files.
"""
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024        # 5 MB
MAX_PIXELS = 40_000_000                   # refuse "decompression bomb" images
MIN_SIDE = 200                            # too small to look good
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
LARGE_SIDE = 1600
THUMB_SIDE = 400


class ImageError(ValueError):
    """The upload can't be used. The message is safe to show to the owner."""


@dataclass(frozen=True)
class PreparedImage:
    large: bytes
    thumb: bytes
    width: int
    height: int


def _encode(image: Image.Image, longest_side: int, quality: int) -> bytes:
    copy = image.copy()
    copy.thumbnail((longest_side, longest_side), Image.Resampling.LANCZOS)
    out = BytesIO()
    copy.save(out, format="WEBP", quality=quality, method=6)  # saving fresh = no metadata carried over
    return out.getvalue()


def prepare_image(data: bytes) -> PreparedImage:
    if not data:
        raise ImageError("The file is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ImageError("Photos must be 5 MB or smaller")
    try:
        with Image.open(BytesIO(data)) as probe:
            if probe.format not in ALLOWED_FORMATS:
                raise ImageError("Use a JPEG, PNG or WebP photo")
            if probe.width * probe.height > MAX_PIXELS:
                raise ImageError("This photo is too large")
            probe.verify()  # detects broken or tampered files
        with Image.open(BytesIO(data)) as image:
            image = ImageOps.exif_transpose(image)  # apply phone rotation before dropping metadata
            image = image.convert("RGB")
    except ImageError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, SyntaxError):
        raise ImageError("This file isn't a valid image")

    if min(image.size) < MIN_SIDE:
        raise ImageError(f"Photos must be at least {MIN_SIDE} pixels on each side")
    large = _encode(image, LARGE_SIDE, quality=82)
    width, height = Image.open(BytesIO(large)).size
    return PreparedImage(large=large, thumb=_encode(image, THUMB_SIDE, quality=75), width=width, height=height)