import logging
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.core.security import verify_hmac_signature
from app.models.booking import Booking
from app.models.payment import Payment
from app.models.webhook_event import WebhookEvent
from app.schemas.payment import WebhookPayload
from app.services.booking_service import BookingService

logger = logging.getLogger(__name__)


class WebhookService:
    def __init__(self, db: Session):
        self.db = db

    def process_webhook(
        self, raw_body: bytes, signature: str, payload: WebhookPayload
    ) -> dict:
        if not verify_hmac_signature(raw_body, signature):
            return {"status": "unauthorized", "http_code": 401}

        webhook_event = WebhookEvent(
            event_id=payload.event_id,
            provider_reference=payload.provider_reference,
            payload=payload.model_dump(),
        )
        self.db.add(webhook_event)
        try:
            self.db.flush()
        except Exception:
            self.db.rollback()
            existing = (
                self.db.query(WebhookEvent)
                .filter(WebhookEvent.event_id == payload.event_id)
                .first()
            )
            if existing:
                return {"status": "duplicate", "http_code": 200}
            raise

        booking = (
            self.db.query(Booking)
            .filter(Booking.id == payload.booking_id)
            .with_for_update()
            .first()
        )
        if booking is None:
            webhook_event.processed_at = datetime.now(UTC)
            webhook_event.outcome = "UNKNOWN_BOOKING"
            self.db.commit()
            return {"status": "not_found", "http_code": 404}

        try:
            payload_amount = Decimal(payload.amount).quantize(Decimal("0.01"))
        except InvalidOperation:
            self.db.rollback()
            logger.warning(
                "Webhook %s has unparseable amount: %r",
                payload.event_id,
                payload.amount,
            )
            return {"status": "invalid_amount", "http_code": 422}
        booking_amount = Decimal(booking.amount).quantize(Decimal("0.01"))
        if payload_amount != booking_amount:
            self.db.rollback()
            logger.warning(
                "Webhook %s amount mismatch: payload=%s booking=%s booking_id=%s",
                payload.event_id,
                payload_amount,
                booking_amount,
                payload.booking_id,
            )
            return {"status": "amount_mismatch", "http_code": 422}

        booking_service = BookingService(self.db)
        try:
            booking_service.transition(
                booking, "CONFIRMED" if payload.status == "SUCCESS" else "FAILED"
            )
            webhook_event.processed_at = datetime.now(UTC)
            webhook_event.outcome = "PROCESSED"
        except ValueError as e:
            webhook_event.processed_at = datetime.now(UTC)
            webhook_event.outcome = "IGNORED"
            logger.warning("Webhook transition ignored: %s", str(e))

        existing_payment = (
            self.db.query(Payment)
            .filter(Payment.provider_reference == payload.provider_reference)
            .first()
        )
        if existing_payment is None:
            payment = Payment(
                booking_id=booking.id,
                user_id=booking.user_id,
                amount=Decimal(payload.amount),
                status=payload.status,
                provider_reference=payload.provider_reference,
            )
            self.db.add(payment)

        self.db.commit()
        return {"status": "processed", "http_code": 200}
