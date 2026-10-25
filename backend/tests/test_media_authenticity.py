"""Tests for rejecting AI-generated photos by their provenance information."""
from io import BytesIO

from PIL import Image
from PIL.PngImagePlugin import PngInfo

from app.media.authenticity import check_provenance


def jpeg(software: str | None = None) -> bytes:
    out = BytesIO()
    exif = Image.Exif()
    if software:
        exif[0x0131] = software
    Image.new("RGB", (400, 300), (120, 140, 160)).save(out, format="JPEG", exif=exif)
    return out.getvalue()


def png(**text_chunks: str) -> bytes:
    info = PngInfo()
    for key, value in text_chunks.items():
        info.add_text(key, value)
    out = BytesIO()
    Image.new("RGB", (400, 300), (120, 140, 160)).save(out, format="PNG", pnginfo=info)
    return out.getvalue()


def with_xmp_source_type(source_type: str) -> bytes:
    xmp = (
        '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description xmlns:Iptc4xmpExt="http://iptc.org/std/Iptc4xmpExt/2008-02-29/" '
        f'Iptc4xmpExt:DigitalSourceType="http://cv.iptc.org/newscodes/digitalsourcetype/{source_type}"/>'
        "</rdf:RDF></x:xmpmeta>"
    )
    info = PngInfo()
    info.add_itxt("XML:com.adobe.xmp", xmp)
    out = BytesIO()
    Image.new("RGB", (400, 300)).save(out, format="PNG", pnginfo=info)
    return out.getvalue()


def test_plain_camera_photo_passes():
    assert not check_provenance(jpeg()).ai_generated


def test_photo_edited_in_normal_software_passes():
    assert not check_provenance(jpeg("Adobe Lightroom Classic 13.0")).ai_generated


def test_real_camera_capture_label_passes():
    assert not check_provenance(with_xmp_source_type("digitalCapture")).ai_generated


def test_ai_generated_label_is_rejected():
    result = check_provenance(with_xmp_source_type("trainedAlgorithmicMedia"))
    assert result.ai_generated and "trainedAlgorithmicMedia" in result.reasons[0]


def test_ai_edited_label_is_rejected():
    assert check_provenance(with_xmp_source_type("compositeWithTrainedAlgorithmicMedia")).ai_generated


def test_generator_named_in_exif_is_rejected():
    result = check_provenance(jpeg("Midjourney v6"))
    assert result.ai_generated and any("midjourney" in r for r in result.reasons)


def test_stable_diffusion_prompt_chunk_is_rejected():
    result = check_provenance(png(parameters="a cosy hair salon, Steps: 30, Sampler: DPM++ 2M"))
    assert result.ai_generated and any("parameters" in r for r in result.reasons)


def test_comfyui_workflow_is_rejected():
    assert check_provenance(png(workflow='{"nodes": []}')).ai_generated


def test_non_image_does_not_crash():
    assert not check_provenance(b"not an image").ai_generated