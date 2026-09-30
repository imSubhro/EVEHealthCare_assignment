import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.booking import Booking
from app.models.payment import Payment

settings = get_settings()


class PaymentService:
    def __init__(self, db: Session):
        self.db = db

    def simulate_payment(
        self,
        booking_id: str,
        user_id: str,
        simulate: str | None = None,
        idempotency_key: str | None = None,
    ) -> tuple[Payment, Booking]:
        booking = (
            self.db.query(Booking)
            .filter(Booking.id == booking_id, Booking.user_id == user_id)
            .first()
        )
        if booking is None:
            raise ValueError("Booking not found")

        if idempotency_key:
            existing = (
                self.db.query(Payment)
                .filter(
                    Payment.user_id == user_id,
                    Payment.idempotency_key == idempotency_key,
                )
                .first()
            )
            if existing:
                return existing, booking

        if booking.status != "PENDING":
            raise ValueError(
                f"Booking is not PENDING (current status: {booking.status})"
            )

        if simulate is None:
            import random

            simulate = (
                "SUCCESS"
                if random.random() < settings.PAYMENT_SUCCESS_RATE
                else "FAILED"
            )

        provider_ref = f"pay_{uuid.uuid4().hex[:12]}"
        payment = Payment(
            booking_id=booking_id,
            user_id=user_id,
            amount=booking.amount,
            status=simulate,
            provider_reference=provider_ref,
            idempotency_key=idempotency_key,
        )
        self.db.add(payment)

        new_status = "CONFIRMED" if simulate == "SUCCESS" else "FAILED"
        booking.status = new_status
        booking.updated_at = datetime.now(UTC)

        self.db.commit()
        self.db.refresh(payment)
        self.db.refresh(booking)
        return payment, booking
