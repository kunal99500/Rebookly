"""guest booking email

Revision ID: guest_booking_email_0010
Revises: d511f28d7b88
Create Date: 2026-11-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "guest_booking_email_0010"
down_revision: Union[str, None] = "d511f28d7b88"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("client_email", sa.String(length=254), nullable=True))


def downgrade() -> None:
    op.drop_column("bookings", "client_email")
