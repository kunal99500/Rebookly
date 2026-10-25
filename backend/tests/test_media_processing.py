"""Tests for photo checks: real images only, metadata removed, resized."""
from io import BytesIO

import pytest
from PIL import Image

from app.media.processing import ImageError, prepare_image


def make_photo(width=1200, height=800, fmt="JPEG", exif=None) -> bytes:
    out = BytesIO()
    image = Image.new("RGB", (width, height), (180, 120, 90))
    kwargs = {"exif": exif} if exif is not None else {}
    image.save(out, format=fmt, **kwargs)
    return out.getvalue()


def photo_with_gps() -> bytes:
    exif = Image.Exif()
    exif[0x8825] = {2: (51.0, 30.0, 0.0), 1: "N", 4: (0.0, 7.0, 0.0), 3: "W"}  # GPS block
    exif[0x010F] = "PhoneMaker"                                              # camera make
    return make_photo(exif=exif)


def test_valid_photo_is_resized_to_webp():
    prepared = prepare_image(make_photo(4000, 3000))
    large = Image.open(BytesIO(prepared.large))
    thumb = Image.open(BytesIO(prepared.thumb))
    assert large.format == "WEBP" and max(large.size) == 1600
    assert thumb.format == "WEBP" and max(thumb.size) == 400
    assert (prepared.width, prepared.height) == large.size


def test_small_photos_are_not_enlarged():
    prepared = prepare_image(make_photo(800, 600))
    assert (prepared.width, prepared.height) == (800, 600)


def test_gps_and_camera_metadata_are_removed():
    source = photo_with_gps()
    assert Image.open(BytesIO(source)).getexif()  # the test photo really has metadata
    prepared = prepare_image(source)
    for version in (prepared.large, prepared.thumb):
        image = Image.open(BytesIO(version))
        assert not image.getexif()
        assert "exif" not in image.info


def test_png_and_webp_are_accepted():
    prepare_image(make_photo(fmt="PNG"))
    prepare_image(make_photo(fmt="WEBP"))


@pytest.mark.parametrize("data, message", [
    (b"", "empty"),
    (b"this is not an image at all", "valid image"),
    (b"%PDF-1.4 fake pdf", "valid image"),
])
def test_non_images_are_rejected(data, message):
    with pytest.raises(ImageError, match=message):
        prepare_image(data)


def test_gif_is_rejected():
    out = BytesIO()
    Image.new("RGB", (400, 400)).save(out, format="GIF")
    with pytest.raises(ImageError, match="JPEG, PNG or WebP"):
        prepare_image(out.getvalue())


def test_tiny_photo_is_rejected():
    with pytest.raises(ImageError, match="at least"):
        prepare_image(make_photo(100, 100))


def test_oversized_file_is_rejected():
    with pytest.raises(ImageError, match="5 MB"):
        prepare_image(b"\xff" * (5 * 1024 * 1024 + 1))