"""One row per call to the AI provider: which feature, which model, how long, how many tokens, success.

No prompts, replies or personal data are stored here; Langfuse holds the detailed traces.
"""
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Identity, Index, Integer, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AIUsage(Base):
    __tablename__ = "ai_usage"
    __table_args__ = (
        Index("ix_ai_usage_business_time", "business_id", "occurred_at"),
        Index("ix_ai_usage_feature_time", "feature", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    feature: Mapped[str] = mapped_column(String(40))          # e.g. "onboarding", "policy_parser"
    model: Mapped[str] = mapped_column(String(80))
    tier: Mapped[str] = mapped_column(String(10))             # "fast" or "smart"
    actor_type: Mapped[str] = mapped_column(String(10))       # owner, client, system
    business_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # no foreign key, like the audit log
    latency_ms: Mapped[int] = mapped_column(Integer)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    attempt: Mapped[int] = mapped_column(SmallInteger, default=1, server_default="1")
    success: Mapped[bool] = mapped_column(Boolean)
    error_type: Mapped[str | None] = mapped_column(String(60))