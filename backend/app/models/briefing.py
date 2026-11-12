"""One saved daily briefing per business per day, so the dashboard doesn't call the AI on every visit."""
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import UUIDPrimaryKey


class DailyBriefing(UUIDPrimaryKey, Base):
    __tablename__ = "daily_briefings"
    __table_args__ = (UniqueConstraint("business_id", "day", name="uq_daily_briefings_business_day"),)

    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"))
    day: Mapped[date] = mapped_column(Date)                    # the business's local date
    content: Mapped[dict] = mapped_column(JSONB)               # summary, highlights, suggestions, numbers
    ai_written: Mapped[bool] = mapped_column(Boolean, default=False)
    refreshes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())