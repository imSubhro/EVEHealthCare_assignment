from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.centre_test import CentreTest


class BookingService:
    def __init__(self, db: Session):
        self.db = db

    def create_booking(
        self, user_id: str, centre_id: str, test_id: str, appointment_at: datetime
    ) -> Booking:
        centre_test = (
            self.db.query(CentreTest)
            .filter(
                CentreTest.centre_id == centre_id,
                CentreTest.test_id == test_id,
                CentreTest.is_active == True,  # noqa: E712
            )
            .first()
        )
        if centre_test is None:
            raise ValueError(
                "Centre does not offer this test or combination is inactive"
            )

        if appointment_at <= datetime.now(UTC):
            raise ValueError("Appointment must be in the future")

        booking = Booking(
            user_id=user_id,
            centre_id=centre_id,
            test_id=test_id,
            appointment_at=appointment_at,
            amount=float(centre_test.price),
            status="PENDING",
        )
        self.db.add(booking)
        self.db.commit()
        self.db.refresh(booking)
        return booking

    def transition(self, booking: Booking, new_status: str) -> Booking:
        allowed = {
            ("PENDING", "CONFIRMED"),
            ("PENDING", "FAILED"),
            ("PENDING", "CANCELLED"),
            ("CONFIRMED", "CANCELLED"),
        }
        if (booking.status, new_status) not in allowed:
            raise ValueError(
                f"Illegal transition from {booking.status} to {new_status}"
            )
        booking.status = new_status
        booking.updated_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(booking)
        return booking

    def cancel_booking(self, booking: Booking) -> Booking:
        return self.transition(booking, "CANCELLED")
