import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    centre_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("diagnostic_centres.id", ondelete="CASCADE"),
        nullable=False,
    )
    test_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("diagnostic_tests.id", ondelete="CASCADE"),
        nullable=False,
    )
    appointment_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("PENDING", "CONFIRMED", "FAILED", "CANCELLED", name="booking_status"),
        default="PENDING",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_bookings_user_created", "user_id", created_at.desc()),
        Index("ix_bookings_status", "status"),
        CheckConstraint("amount > 0", name="ck_bookings_amount_positive"),
    )
