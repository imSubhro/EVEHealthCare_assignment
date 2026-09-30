from datetime import datetime

from pydantic import BaseModel, Field


class BookingCreate(BaseModel):
    centre_id: str
    test_id: str
    appointment_at: datetime


class PaymentBrief(BaseModel):
    id: str
    status: str
    amount: float
    provider_reference: str
    created_at: datetime

    model_config = {"from_attributes": True}


class BookingResponse(BaseModel):
    id: str
    user_id: str
    centre_id: str
    test_id: str
    appointment_at: datetime
    amount: float
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BookingDetailResponse(BookingResponse):
    payments: list[PaymentBrief] = Field(default_factory=list)
