import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.schemas.payment import PaymentCreate, PaymentResponse, WebhookPayload
from app.services.payment_service import PaymentService
from app.services.webhook_service import WebhookService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def create_payment(
    data: PaymentCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    service = PaymentService(db)
    try:
        payment, booking = service.simulate_payment(
            booking_id=str(data.booking_id),
            user_id=current_user.id,
            simulate=data.simulate,
            idempotency_key=idempotency_key,
        )
    except ValueError as e:
        error_code = (
            "BOOKING_NOT_FOUND" if "not found" in str(e).lower() else "PAYMENT_ERROR"
        )
        http_code = (
            status.HTTP_404_NOT_FOUND
            if error_code == "BOOKING_NOT_FOUND"
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(
            status_code=http_code,
            detail={"detail": str(e), "code": error_code},
        )
    return PaymentResponse(
        payment_id=payment.id,
        status=payment.status,
        booking_status=booking.status,
    )


@router.post("/webhook/")
async def payment_webhook(
    request: Request,
    x_signature: str = Header(..., alias="X-Signature"),
    db: Session = Depends(get_db),
):
    raw_body = await request.body()
    try:
        payload_data = await request.json()
        payload = WebhookPayload(**payload_data)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"detail": "Invalid webhook payload", "code": "INVALID_PAYLOAD"},
        )

    service = WebhookService(db)
    result = service.process_webhook(raw_body, x_signature, payload)

    if result["http_code"] == 401:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Invalid signature", "code": "INVALID_SIGNATURE"},
        )
    if result["http_code"] == 404:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Booking not found", "code": "BOOKING_NOT_FOUND"},
        )
    if result["http_code"] == 422:
        code = (
            "AMOUNT_MISMATCH"
            if result["status"] == "amount_mismatch"
            else "INVALID_PAYLOAD"
        )
        detail = (
            "Webhook amount does not match booking amount"
            if code == "AMOUNT_MISMATCH"
            else "Invalid webhook amount"
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"detail": detail, "code": code},
        )
    return {"status": result["status"]}
