"""Speech to text for the microphone buttons (owners and clients)."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel

from app.ai.transcription import ALLOWED_TYPES, MAX_AUDIO_BYTES, TranscriptionError, VoiceLimiter
from app.auth.dependencies import get_current_user
from app.auth.supabase_auth import AuthUser

router = APIRouter(prefix="/api/voice", tags=["voice"])
_limiter = VoiceLimiter()

HINTS = {
    "onboarding": "A small business owner describing their business, services, prices and opening hours.",
    "assistant": "A client asking about their appointment booking.",
}


class TranscriptOut(BaseModel):
    text: str


@router.post("/transcribe", response_model=TranscriptOut)
async def transcribe(
    request: Request,
    audio: UploadFile = File(description="A short recording (webm, ogg, mp4, m4a, mp3 or wav), up to 10 MB"),
    context: str = Form("onboarding", pattern="^(onboarding|assistant|other)$"),
    user: AuthUser = Depends(get_current_user),
):
    """Turn a short recording into text, in whatever language was spoken. Nothing is stored."""
    transcriber = getattr(request.app.state, "transcriber", None)
    if transcriber is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Voice input isn’t available right now. Please type instead.")
    content_type = (audio.content_type or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "That recording format isn’t supported.")
    if not _limiter.allow(str(user.id)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "That’s a lot of recordings. Please type for a while.")
    data = await audio.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "That recording is too long. Keep it under 5 minutes.")
    if len(data) < 1000:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "We didn’t catch anything. Try again a little closer to the mic.")
    try:
        text = await transcriber.transcribe(data, content_type, HINTS.get(context))
    except TranscriptionError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "We couldn’t understand the recording. Please try again or type.")
    if not text:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "We didn’t catch any words. Try again.")
    return TranscriptOut(text=text)
