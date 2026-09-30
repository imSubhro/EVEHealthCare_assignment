import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class CentreTest(Base):
    __tablename__ = "centre_tests"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
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
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        CheckConstraint("price > 0", name="ck_centre_tests_price_positive"),
    )
