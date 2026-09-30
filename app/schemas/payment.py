from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class PaymentCreate(BaseModel):
    booking_id: UUID
    simulate: str | None = None


class PaymentResponse(BaseModel):
    payment_id: str
    status: str
    booking_status: str

    model_config = {"from_attributes": True}


class WebhookPayload(BaseModel):
    event_id: str
    provider_reference: str
    booking_id: str
    status: Literal["SUCCESS", "FAILED"]
    amount: str
    occurred_at: str
