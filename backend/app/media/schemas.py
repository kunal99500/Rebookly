"""What the API returns for photos, and what can be changed after upload."""
import uuid

from pydantic import BaseModel, ConfigDict, Field


class PhotoOut(BaseModel):
    id: uuid.UUID
    kind: str
    service_id: uuid.UUID | None
    url: str
    thumb_url: str
    width: int
    height: int
    alt_text: str | None
    sort_order: int


class PhotoUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    alt_text: str | None = Field(default=None, max_length=200)
    sort_order: int | None = Field(default=None, ge=0, le=100)
    moderation_status: str = Field(default="pending")