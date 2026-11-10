"""flexible appointments

Revision ID: c6a71ec30ac4
Revises: 993144b15597
"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "c6a71ec30ac4"
down_revision: Union[str, None] = "993144b15597"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

from alembic import op
import sqlalchemy as sa

NEW_TABLES = ("locations", "staff", "staff_services", "staff_hours", "time_off", "resources", "booking_items")


def upgrade() -> None:
    # ---------- 1. New tables ----------
    op.create_table(
        "locations",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], name=op.f("fk_locations_business_id_businesses"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_locations")),
    )
    op.create_index(op.f("ix_locations_business_id"), "locations", ["business_id"], unique=False)
    op.create_index("uq_locations_one_primary", "locations", ["business_id"], unique=True, postgresql_where=sa.text("is_primary"))

    op.create_table(
        "staff",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("auth_user_id", sa.UUID(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], name=op.f("fk_staff_business_id_businesses"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], name=op.f("fk_staff_location_id_locations"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_staff")),
    )
    op.create_index(op.f("ix_staff_business_id"), "staff", ["business_id"], unique=False)

    op.create_table(
        "staff_services",
        sa.Column("staff_id", sa.UUID(), nullable=False),
        sa.Column("service_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], name=op.f("fk_staff_services_service_id_services"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"], name=op.f("fk_staff_services_staff_id_staff"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("staff_id", "service_id", name=op.f("pk_staff_services")),
    )
    op.create_index(op.f("ix_staff_services_service_id"), "staff_services", ["service_id"], unique=False)

    op.create_table(
        "staff_hours",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("staff_id", sa.UUID(), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("end_time > start_time", name=op.f("ck_staff_hours_ends_after_start")),
        sa.CheckConstraint("weekday BETWEEN 0 AND 6", name=op.f("ck_staff_hours_weekday_range")),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"], name=op.f("fk_staff_hours_staff_id_staff"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_staff_hours")),
    )
    op.create_index(op.f("ix_staff_hours_staff_id"), "staff_hours", ["staff_id"], unique=False)

    op.create_table(
        "time_off",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("staff_id", sa.UUID(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("ends_at > starts_at", name=op.f("ck_time_off_ends_after_start")),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], name=op.f("fk_time_off_business_id_businesses"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"], name=op.f("fk_time_off_staff_id_staff"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_time_off")),
    )
    op.create_index("ix_time_off_business_start", "time_off", ["business_id", "starts_at"], unique=False)

    op.create_table(
        "resources",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], name=op.f("fk_resources_business_id_businesses"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], name=op.f("fk_resources_location_id_locations"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_resources")),
    )
    op.create_index(op.f("ix_resources_business_id"), "resources", ["business_id"], unique=False)

    op.create_table(
        "booking_items",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("booking_id", sa.UUID(), nullable=False),
        sa.Column("service_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("deposit", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("kind IN ('main', 'add_on')", name=op.f("ck_booking_items_kind_valid")),
        sa.CheckConstraint("duration_minutes > 0", name=op.f("ck_booking_items_duration_positive")),
        sa.CheckConstraint("price >= 0 AND deposit >= 0", name=op.f("ck_booking_items_amounts_not_negative")),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], name=op.f("fk_booking_items_booking_id_bookings"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], name=op.f("fk_booking_items_service_id_services"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_booking_items")),
        sa.UniqueConstraint("booking_id", "position", name="uq_booking_items_booking_position"),
    )
    op.create_index(op.f("ix_booking_items_booking_id"), "booking_items", ["booking_id"], unique=False)

    # ---------- 2. New columns ----------
    op.add_column("businesses", sa.Column("start_interval_minutes", sa.Integer(), server_default="15", nullable=False))
    op.add_column("businesses", sa.Column("min_notice_minutes", sa.Integer(), server_default="60", nullable=False))
    op.create_check_constraint(op.f("ck_businesses_start_interval_valid"), "businesses",
                               "start_interval_minutes IN (5, 10, 15, 20, 30, 60)")
    op.create_check_constraint(op.f("ck_businesses_min_notice_range"), "businesses", "min_notice_minutes BETWEEN 0 AND 10080")

    op.add_column("services", sa.Column("kind", sa.String(length=10), server_default="main", nullable=False))
    op.add_column("services", sa.Column("booking_mode", sa.String(length=12), server_default="appointment", nullable=False))
    op.add_column("services", sa.Column("cleanup_minutes", sa.Integer(), server_default="0", nullable=False))
    op.create_check_constraint(op.f("ck_services_kind_valid"), "services", "kind IN ('main', 'add_on')")
    op.create_check_constraint(op.f("ck_services_booking_mode_valid"), "services", "booking_mode IN ('appointment', 'class')")
    op.create_check_constraint(op.f("ck_services_cleanup_range"), "services", "cleanup_minutes BETWEEN 0 AND 240")

    op.add_column("bookings", sa.Column("location_id", sa.UUID(), nullable=True))
    op.add_column("bookings", sa.Column("staff_id", sa.UUID(), nullable=True))
    op.add_column("bookings", sa.Column("occupied_until", sa.DateTime(timezone=True), nullable=True))  # filled below
    op.alter_column("bookings", "slot_id", existing_type=sa.UUID(), nullable=True)
    op.create_foreign_key(op.f("fk_bookings_location_id_locations"), "bookings", "locations", ["location_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key(op.f("fk_bookings_staff_id_staff"), "bookings", "staff", ["staff_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_bookings_staff_start", "bookings", ["staff_id", "starts_at"], unique=False)

    # ---------- 3. Fill in data for existing businesses and bookings ----------
    # Every business gets a primary location and one staff member (the owner), who does every service.
    op.execute("""
        INSERT INTO locations (business_id, name, is_primary)
        SELECT id, 'Main', true FROM businesses
    """)
    op.execute("""
        INSERT INTO staff (business_id, location_id, name, auth_user_id)
        SELECT b.id, l.id, b.name, b.owner_user_id
        FROM businesses b JOIN locations l ON l.business_id = b.id AND l.is_primary
    """)
    op.execute("""
        INSERT INTO staff_services (staff_id, service_id)
        SELECT st.id, sv.id FROM staff st JOIN services sv ON sv.business_id = st.business_id
    """)
    # Existing bookings: link them to that staff member and location, and record each as one item.
    op.execute("""
        UPDATE bookings b SET staff_id = st.id, location_id = st.location_id, occupied_until = b.ends_at
        FROM staff st WHERE st.business_id = b.business_id
    """)
    op.execute("UPDATE bookings SET occupied_until = ends_at WHERE occupied_until IS NULL")
    # Every existing service is an appointment service, so its bookings no longer use pre-made slots.
    op.execute("UPDATE bookings SET slot_id = NULL")
    op.execute("""
        INSERT INTO booking_items (booking_id, service_id, position, kind, name, duration_minutes, price, deposit)
        SELECT b.id, b.service_id, 1, 'main', s.name, s.duration_minutes, b.price, s.deposit
        FROM bookings b JOIN services s ON s.id = b.service_id
    """)
    op.alter_column("bookings", "occupied_until", existing_type=sa.DateTime(timezone=True), nullable=False)
    op.create_check_constraint(op.f("ck_bookings_occupied_after_end"), "bookings", "occupied_until >= ends_at")

    # ---------- 4. The database refuses overlapping appointments for the same staff member ----------
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute("""
        ALTER TABLE bookings ADD CONSTRAINT ex_bookings_staff_no_overlap
        EXCLUDE USING gist (staff_id WITH =, tstzrange(starts_at, occupied_until) WITH &&)
        WHERE (status IN ('pending_payment', 'confirmed') AND staff_id IS NOT NULL AND slot_id IS NULL)
    """)

    # ---------- 5. Block Supabase's public API from the new tables ----------
    for table in NEW_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE bookings DROP CONSTRAINT IF EXISTS ex_bookings_staff_no_overlap")
    op.drop_constraint(op.f("ck_bookings_occupied_after_end"), "bookings", type_="check")
    op.drop_index("ix_bookings_staff_start", table_name="bookings")
    op.drop_constraint(op.f("fk_bookings_staff_id_staff"), "bookings", type_="foreignkey")
    op.drop_constraint(op.f("fk_bookings_location_id_locations"), "bookings", type_="foreignkey")
    op.drop_column("bookings", "occupied_until")
    op.drop_column("bookings", "staff_id")
    op.drop_column("bookings", "location_id")
    # Note: slot_id stays nullable; appointment bookings made after the upgrade have no slot.

    op.drop_constraint(op.f("ck_services_cleanup_range"), "services", type_="check")
    op.drop_constraint(op.f("ck_services_booking_mode_valid"), "services", type_="check")
    op.drop_constraint(op.f("ck_services_kind_valid"), "services", type_="check")
    op.drop_column("services", "cleanup_minutes")
    op.drop_column("services", "booking_mode")
    op.drop_column("services", "kind")

    op.drop_constraint(op.f("ck_businesses_min_notice_range"), "businesses", type_="check")
    op.drop_constraint(op.f("ck_businesses_start_interval_valid"), "businesses", type_="check")
    op.drop_column("businesses", "min_notice_minutes")
    op.drop_column("businesses", "start_interval_minutes")

    for table in reversed(NEW_TABLES):
        op.drop_table(table)