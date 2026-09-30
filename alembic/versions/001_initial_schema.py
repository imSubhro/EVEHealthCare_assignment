"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-09-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    booking_status = sa.Enum("PENDING", "CONFIRMED", "FAILED", "CANCELLED", name="booking_status")
    payment_status = sa.Enum("SUCCESS", "FAILED", name="payment_status")

    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "diagnostic_centres",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_centres_city", "diagnostic_centres", ["city"])
    op.create_index("uq_centres_name_city", "diagnostic_centres", ["name", "city"], unique=True)

    op.create_table(
        "diagnostic_tests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), unique=True, nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "centre_tests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("centre_id", sa.String(36), sa.ForeignKey("diagnostic_centres.id", ondelete="CASCADE"), nullable=False),
        sa.Column("test_id", sa.String(36), sa.ForeignKey("diagnostic_tests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("price > 0", name="ck_centre_tests_price_positive"),
    )
    op.create_index("uq_centre_test", "centre_tests", ["centre_id", "test_id"], unique=True)

    op.create_table(
        "bookings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("centre_id", sa.String(36), sa.ForeignKey("diagnostic_centres.id", ondelete="CASCADE"), nullable=False),
        sa.Column("test_id", sa.String(36), sa.ForeignKey("diagnostic_tests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("appointment_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", booking_status, nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("amount > 0", name="ck_bookings_amount_positive"),
    )
    op.create_index("ix_bookings_user_created", "bookings", ["user_id", sa.text("created_at DESC")])
    op.create_index("ix_bookings_status", "bookings", ["status"])

    op.create_table(
        "payments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("booking_id", sa.String(36), sa.ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", payment_status, nullable=False),
        sa.Column("provider_reference", sa.String(255), unique=True, nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_payments_booking_id", "payments", ["booking_id"])
    op.create_index("ix_payments_user_id", "payments", ["user_id"])
    op.create_index(
        "uq_payments_user_idempotency",
        "payments",
        ["user_id", "idempotency_key"],
        unique=True,
        postgresql_where="idempotency_key IS NOT NULL",
    )

    op.create_table(
        "webhook_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_id", sa.String(255), unique=True, nullable=False),
        sa.Column("provider_reference", sa.String(255), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("webhook_events")
    op.drop_table("payments")
    op.drop_table("bookings")
    op.drop_table("centre_tests")
    op.drop_table("diagnostic_tests")
    op.drop_table("diagnostic_centres")
    op.drop_table("users")
    sa.Enum(name="booking_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="payment_status").drop(op.get_bind(), checkfirst=True)
