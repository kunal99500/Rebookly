"""Speech to text for the microphone buttons. Any language; the speaker's language is detected automatically.

The recording is sent to the AI provider, turned into text and then forgotten: neither the audio nor the text
is stored here. The text goes back to the person to check before they send it.
"""
import time
from collections import defaultdict, deque

from openai import AsyncOpenAI

MAX_AUDIO_BYTES = 10 * 1024 * 1024          # about 5 minutes of compressed speech
ALLOWED_TYPES = {"audio/webm", "audio/ogg", "audio/mp4", "audio/mpeg", "audio/wav", "audio/x-wav", "audio/m4a",
                 "audio/x-m4a", "audio/aac", "video/webm"}
EXTENSIONS = {"audio/webm": "webm", "video/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "mp4", "audio/mpeg": "mp3",
              "audio/wav": "wav", "audio/x-wav": "wav", "audio/m4a": "m4a", "audio/x-m4a": "m4a", "audio/aac": "aac"}


class TranscriptionError(Exception):
    pass


class Transcriber:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini-transcribe", timeout: float = 60):
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout, max_retries=1)
        self._model = model

    async def transcribe(self, audio: bytes, content_type: str, hint: str | None = None) -> str:
        """[hint] can name the context ("a business owner describing their salon") to improve accuracy."""
        base_type = content_type.split(";")[0].strip().lower()
        try:
            result = await self._client.audio.transcriptions.create(
                model=self._model,
                file=(f"speech.{EXTENSIONS.get(base_type, 'webm')}", audio, base_type),
                prompt=hint or None,
            )
        except Exception as error:   # network, provider or format problem
            raise TranscriptionError(str(error)) from error
        return (getattr(result, "text", "") or "").strip()


class VoiceLimiter:
    """Each signed-in person can transcribe up to [limit] recordings an hour."""

    def __init__(self, limit: int = 60, window_seconds: int = 3600):
        self.limit, self.window = limit, window_seconds
        self._seen: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        recent = self._seen[key]
        while recent and now - recent[0] > self.window:
            recent.popleft()
        if len(recent) >= self.limit:
            return False
        recent.append(now)
        return True
