from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.booking import Booking
from app.models.payment import Payment
from app.schemas.booking import (
    BookingCreate,
    BookingDetailResponse,
    BookingResponse,
    PaymentBrief,
)
from app.services.booking_service import BookingService

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
def create_booking(
    data: BookingCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = BookingService(db)
    try:
        booking = service.create_booking(
            user_id=current_user.id,
            centre_id=data.centre_id,
            test_id=data.test_id,
            appointment_at=data.appointment_at,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"detail": str(e), "code": "BOOKING_ERROR"},
        )
    return booking


@router.get("", response_model=list[BookingResponse])
def list_bookings(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(Booking).filter(Booking.user_id == current_user.id)
    if status_filter:
        query = query.filter(Booking.status == status_filter)
    bookings = (
        query.order_by(Booking.created_at.desc()).offset(offset).limit(limit).all()
    )
    return bookings


@router.get("/{booking_id}", response_model=BookingDetailResponse)
def get_booking(
    booking_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    booking = (
        db.query(Booking)
        .filter(Booking.id == str(booking_id), Booking.user_id == current_user.id)
        .first()
    )
    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Booking not found", "code": "BOOKING_NOT_FOUND"},
        )
    payments = (
        db.query(Payment)
        .filter(Payment.booking_id == booking.id)
        .order_by(Payment.created_at)
        .all()
    )
    detail = BookingDetailResponse.model_validate(booking)
    detail.payments = [PaymentBrief.model_validate(p) for p in payments]
    return detail


@router.post("/{booking_id}/cancel", response_model=BookingResponse)
def cancel_booking(
    booking_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    booking = (
        db.query(Booking)
        .filter(Booking.id == str(booking_id), Booking.user_id == current_user.id)
        .first()
    )
    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Booking not found", "code": "BOOKING_NOT_FOUND"},
        )
    service = BookingService(db)
    try:
        booking = service.cancel_booking(booking)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"detail": str(e), "code": "ILLEGAL_TRANSITION"},
        )
    return booking
