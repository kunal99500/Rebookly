"""Rejects AI-generated and AI-edited photos, using the provenance information files carry.

What this can detect reliably:
  * Content Credentials (C2PA) and IPTC/XMP "digital source type" labels that AI tools such as
    ChatGPT/DALL-E, Adobe Firefly, Microsoft Designer and Google's tools write into their images.
  * Generator names and prompts written by tools like Midjourney, Stable Diffusion and ComfyUI.

What it can't: an AI image whose metadata was removed (for example by taking a screenshot).
That's why uploads also require the owner's confirmation, and clients can report photos.
Runs on the ORIGINAL file, before processing strips the metadata away.
"""
from dataclasses import dataclass, field
from io import BytesIO

from PIL import Image, UnidentifiedImageError

# IPTC "digital source type" values meaning the image was made or edited by generative AI.
AI_SOURCE_TYPES = (
    b"trainedAlgorithmicMedia",               # fully AI-generated
    b"compositeWithTrainedAlgorithmicMedia",  # real photo with AI-generated parts (e.g. generative fill)
    b"compositeSynthetic",
)

# Names of AI image tools, as they appear in "Software" / "CreatorTool" fields and text chunks.
GENERATOR_NAMES = (
    "midjourney", "dall-e", "dall·e", "dalle", "openai", "chatgpt", "gpt-4o", "stable diffusion",
    "stablediffusion", "sdxl", "automatic1111", "comfyui", "invokeai", "novelai", "adobe firefly",
    "firefly", "imagen", "ideogram", "leonardo.ai", "playground ai", "bing image creator",
    "microsoft designer", "flux.1", "black forest labs", "runway", "nightcafe", "dreamstudio",
)

# Text-chunk keys that image generators write (e.g. Stable Diffusion's prompt and settings).
GENERATOR_KEYS = ("parameters", "prompt", "workflow", "negative_prompt", "sd-metadata", "invokeai_metadata")

EXIF_TEXT_TAGS = (0x0131, 0x010E, 0x013B, 0x9286)  # Software, ImageDescription, Artist, UserComment


@dataclass(frozen=True)
class ProvenanceResult:
    ai_generated: bool
    reasons: list[str] = field(default_factory=list)


def _contains_generator_name(text: str) -> str | None:
    lowered = text.lower()
    return next((name for name in GENERATOR_NAMES if name in lowered), None)


def check_provenance(data: bytes) -> ProvenanceResult:
    reasons: list[str] = []

    # 1. Content Credentials / XMP labels. These are stored as plain text inside the file,
    #    so a byte search finds them in JPEG, PNG and WebP alike.
    for marker in AI_SOURCE_TYPES:
        if marker in data:
            reasons.append(f"provenance label: {marker.decode()}")
            break

    # 2. Generator names and prompts in the file's metadata fields.
    try:
        with Image.open(BytesIO(data)) as image:
            for key, value in image.info.items():
                if isinstance(key, str) and key.lower() in GENERATOR_KEYS:
                    reasons.append(f"generator metadata field: {key}")
                if isinstance(value, (str, bytes)):
                    text = value.decode("utf-8", "ignore") if isinstance(value, bytes) else value
                    name = _contains_generator_name(text)
                    if name:
                        reasons.append(f"generator named in metadata: {name}")
            exif = image.getexif()
            for tag in EXIF_TEXT_TAGS:
                value = exif.get(tag)
                if isinstance(value, bytes):
                    value = value.decode("utf-8", "ignore")
                if isinstance(value, str):
                    name = _contains_generator_name(value)
                    if name:
                        reasons.append(f"generator named in EXIF: {name}")
    except (UnidentifiedImageError, OSError, SyntaxError):
        pass  # not an image; processing.py rejects it with a clear message

    unique = list(dict.fromkeys(reasons))
    return ProvenanceResult(ai_generated=bool(unique), reasons=unique)