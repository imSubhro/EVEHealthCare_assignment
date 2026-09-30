import pytest

from app.services.booking_service import BookingService


class FakeBooking:
    def __init__(self, status="PENDING"):
        self.status = status
        self.updated_at = None


class FakeDB:
    def commit(self):
        pass

    def refresh(self, obj):
        pass


class FakeBookingService(BookingService):
    def __init__(self):
        self.db = FakeDB()


def test_pending_to_confirmed():
    svc = FakeBookingService()
    booking = FakeBooking("PENDING")
    result = svc.transition(booking, "CONFIRMED")
    assert result.status == "CONFIRMED"


def test_pending_to_failed():
    svc = FakeBookingService()
    booking = FakeBooking("PENDING")
    result = svc.transition(booking, "FAILED")
    assert result.status == "FAILED"


def test_pending_to_cancelled():
    svc = FakeBookingService()
    booking = FakeBooking("PENDING")
    result = svc.transition(booking, "CANCELLED")
    assert result.status == "CANCELLED"


def test_confirmed_to_cancelled():
    svc = FakeBookingService()
    booking = FakeBooking("CONFIRMED")
    result = svc.transition(booking, "CANCELLED")
    assert result.status == "CANCELLED"


def test_confirmed_to_pending_raises():
    svc = FakeBookingService()
    booking = FakeBooking("CONFIRMED")
    with pytest.raises(ValueError):
        svc.transition(booking, "PENDING")


def test_failed_to_any_raises():
    svc = FakeBookingService()
    for status in ["PENDING", "CONFIRMED", "CANCELLED", "FAILED"]:
        booking = FakeBooking("FAILED")
        with pytest.raises(ValueError):
            svc.transition(booking, status)


def test_cancelled_to_any_raises():
    svc = FakeBookingService()
    for status in ["PENDING", "CONFIRMED", "CANCELLED", "FAILED"]:
        booking = FakeBooking("CANCELLED")
        with pytest.raises(ValueError):
            svc.transition(booking, status)
