"""tax fields on booking items

Revision ID: 67c423d676a1
Revises: 1a1d791fc692
Create Date: 2026-11-10 19:37:47.177297

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '67c423d676a1'
down_revision: Union[str, None] = '1a1d791fc692'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("booking_items", sa.Column("tax_rate", sa.Numeric(precision=5, scale=2), nullable=True))
    op.add_column("booking_items", sa.Column("tax_amount", sa.Numeric(precision=10, scale=2), server_default="0", nullable=False))
    op.add_column("booking_items", sa.Column("price_includes_tax", sa.Boolean(), nullable=True))
    op.create_check_constraint(op.f("ck_booking_items_tax_rate_range"), "booking_items",
                               "tax_rate IS NULL OR tax_rate BETWEEN 0 AND 100")
    op.create_check_constraint(op.f("ck_booking_items_tax_amount_not_negative"), "booking_items", "tax_amount >= 0")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_booking_items_tax_amount_not_negative"), "booking_items", type_="check")
    op.drop_constraint(op.f("ck_booking_items_tax_rate_range"), "booking_items", type_="check")
    op.drop_column("booking_items", "price_includes_tax")
    op.drop_column("booking_items", "tax_amount")
    op.drop_column("booking_items", "tax_rate")
