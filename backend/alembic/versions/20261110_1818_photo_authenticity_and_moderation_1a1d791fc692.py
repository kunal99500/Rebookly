"""photo authenticity and moderation

Revision ID: 1a1d791fc692
Revises: c6a71ec30ac4
Create Date: 2026-11-10 18:18:45.769933

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1a1d791fc692'
down_revision: Union[str, None] = 'c6a71ec30ac4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Existing photos get today's date as their confirmation time, so the column can be required.
    op.add_column(
        "business_photos",
        sa.Column("attested_real_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.alter_column("business_photos", "attested_real_at", server_default=None)

    op.add_column(
        "business_photos",
        sa.Column("moderation_status", sa.String(length=10), server_default="approved", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_business_photos_moderation_status_valid"),
        "business_photos",
        "moderation_status IN ('approved', 'flagged', 'hidden')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_business_photos_moderation_status_valid"), "business_photos", type_="check")
    op.drop_column("business_photos", "moderation_status")
    op.drop_column("business_photos", "attested_real_at")