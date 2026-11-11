"""business location

Revision ID: cf90fa214ab9
Revises: f0776258edbf
Create Date: 2026-11-11 12:13:42.071894

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cf90fa214ab9'
down_revision: Union[str, None] = 'f0776258edbf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
LOCATION_COLUMNS = (
    ("country_code", "VARCHAR(2)"),
    ("region_code", "VARCHAR(10)"),
    ("city", "VARCHAR(100)"),
    ("postal_code", "VARCHAR(20)"),
    ("location_source", "VARCHAR(10)"),
)

CHECK_RULES = (
    ("ck_businesses_country_code_format", "country_code IS NULL OR country_code ~ '^[A-Z]{2}$'"),
    ("ck_businesses_location_source_valid",
     "location_source IS NULL OR location_source IN ('gps', 'search', 'manual')"),
    ("ck_businesses_coordinates_together", "(latitude IS NULL) = (longitude IS NULL)"),
)


def upgrade() -> None:
    # Safe to run whatever is already there: an earlier migration may have added some of these.
    for column, sql_type in LOCATION_COLUMNS:
        op.execute(f"ALTER TABLE businesses ADD COLUMN IF NOT EXISTS {column} {sql_type}")

    for name, rule in CHECK_RULES:
        op.execute(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '{name}') THEN
                    ALTER TABLE businesses ADD CONSTRAINT {name} CHECK ({rule});
                END IF;
            END $$;
        """)


def downgrade() -> None:
    for name, _ in CHECK_RULES:
        op.execute(f"ALTER TABLE businesses DROP CONSTRAINT IF EXISTS {name}")
    for column, _ in reversed(LOCATION_COLUMNS):
        op.execute(f"ALTER TABLE businesses DROP COLUMN IF EXISTS {column}")