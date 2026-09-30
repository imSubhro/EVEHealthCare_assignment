import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.user import User
from tests.conftest import make_auth_header

settings = get_settings()


def create_test_user(db, user_id="user-test-id", email="user@test.com", is_admin=False):
    user = User(
        id=user_id,
        email=email,
        full_name="Test User",
        password_hash="hashed",
        is_admin=is_admin,
    )
    db.add(user)
    db.commit()
    return user


def create_admin_user(db):
    return create_test_user(
        db, user_id="admin-test-id", email="admin@test.com", is_admin=True
    )


def setup_booking(client, db):
    admin = create_admin_user(db)
    user = create_test_user(db)

    centre_resp = client.post(
        "/centres",
        json={"name": "Test Centre", "city": "Mumbai", "address": "123 Street"},
        headers=make_auth_header(create_access_token(admin.id, is_admin=True)),
    )
    centre_id = centre_resp.json()["id"]

    test_resp = client.post(
        "/tests",
        json={"name": "Blood Test", "description": "Complete blood count"},
        headers=make_auth_header(create_access_token(admin.id, is_admin=True)),
    )
    test_id = test_resp.json()["id"]

    client.post(
        f"/centres/{centre_id}/tests",
        json={"test_id": test_id, "price": 500.00},
        headers=make_auth_header(create_access_token(admin.id, is_admin=True)),
    )

    future_date = (datetime.now(UTC) + timedelta(days=7)).isoformat()
    booking_resp = client.post(
        "/bookings",
        json={
            "centre_id": centre_id,
            "test_id": test_id,
            "appointment_at": future_date,
        },
        headers=make_auth_header(create_access_token(user.id)),
    )
    return user, booking_resp.json()


def sign_body(body: bytes) -> str:
    return hmac.new(settings.WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


def test_webhook_valid_event(client, db):
    user, booking = setup_booking(client, db)
    payload = {
        "event_id": "evt_001",
        "provider_reference": "pay_abc123",
        "booking_id": booking["id"],
        "status": "SUCCESS",
        "amount": "500.00",
        "occurred_at": datetime.now(UTC).isoformat(),
    }
    body = json.dumps(payload).encode()
    signature = sign_body(body)
    resp = client.post(
        "/payments/webhook/",
        content=body,
        headers={"X-Signature": signature, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "processed"


def test_webhook_bad_signature(client, db):
    user, booking = setup_booking(client, db)
    payload = {
        "event_id": "evt_002",
        "provider_reference": "pay_def456",
        "booking_id": booking["id"],
        "status": "SUCCESS",
        "amount": "500.00",
        "occurred_at": datetime.now(UTC).isoformat(),
    }
    body = json.dumps(payload).encode()
    resp = client.post(
        "/payments/webhook/",
        content=body,
        headers={"X-Signature": "badsignature", "Content-Type": "application/json"},
    )
    assert resp.status_code == 401


def test_webhook_duplicate_event(client, db):
    user, booking = setup_booking(client, db)
    payload = {
        "event_id": "evt_003",
        "provider_reference": "pay_ghi789",
        "booking_id": booking["id"],
        "status": "SUCCESS",
        "amount": "500.00",
        "occurred_at": datetime.now(UTC).isoformat(),
    }
    body = json.dumps(payload).encode()
    signature = sign_body(body)
    headers = {"X-Signature": signature, "Content-Type": "application/json"}

    resp1 = client.post("/payments/webhook/", content=body, headers=headers)
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "processed"

    resp2 = client.post("/payments/webhook/", content=body, headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "duplicate"


def test_webhook_unknown_booking(client, db):
    payload = {
        "event_id": "evt_004",
        "provider_reference": "pay_xyz",
        "booking_id": "non-existent-booking-id",
        "status": "SUCCESS",
        "amount": "500.00",
        "occurred_at": datetime.now(UTC).isoformat(),
    }
    body = json.dumps(payload).encode()
    signature = sign_body(body)
    resp = client.post(
        "/payments/webhook/",
        content=body,
        headers={"X-Signature": signature, "Content-Type": "application/json"},
    )
    assert resp.status_code == 404


def test_webhook_late_success_on_cancelled(client, db):
    user, booking = setup_booking(client, db)

    token = create_access_token(user.id)
    client.post(
        f"/bookings/{booking['id']}/cancel",
        headers=make_auth_header(token),
    )

    payload = {
        "event_id": "evt_005",
        "provider_reference": "pay_late",
        "booking_id": booking["id"],
        "status": "SUCCESS",
        "amount": "500.00",
        "occurred_at": datetime.now(UTC).isoformat(),
    }
    body = json.dumps(payload).encode()
    signature = sign_body(body)
    resp = client.post(
        "/payments/webhook/",
        content=body,
        headers={"X-Signature": signature, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "processed"


def test_webhook_amount_mismatch(client, db):
    user, booking = setup_booking(client, db)
    payload = {
        "event_id": "evt_006",
        "provider_reference": "pay_mismatch",
        "booking_id": booking["id"],
        "status": "SUCCESS",
        "amount": "999.00",
        "occurred_at": datetime.now(UTC).isoformat(),
    }
    body = json.dumps(payload).encode()
    signature = sign_body(body)
    resp = client.post(
        "/payments/webhook/",
        content=body,
        headers={"X-Signature": signature, "Content-Type": "application/json"},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "AMOUNT_MISMATCH"

    booking_after = client.get(
        f"/bookings/{booking['id']}",
        headers=make_auth_header(create_access_token(user.id)),
    )
    assert booking_after.json()["status"] == "PENDING"

    retry_payload = dict(payload)
    retry_body = json.dumps(retry_payload).encode()
    retry_resp = client.post(
        "/payments/webhook/",
        content=retry_body,
        headers={"X-Signature": sign_body(retry_body), "Content-Type": "application/json"},
    )
    assert retry_resp.status_code == 422


def test_webhook_failed_after_success_not_downgraded(client, db):
    user, booking = setup_booking(client, db)

    success_payload = {
        "event_id": "evt_007",
        "provider_reference": "pay_seq_success",
        "booking_id": booking["id"],
        "status": "SUCCESS",
        "amount": "500.00",
        "occurred_at": datetime.now(UTC).isoformat(),
    }
    body = json.dumps(success_payload).encode()
    resp = client.post(
        "/payments/webhook/",
        content=body,
        headers={"X-Signature": sign_body(body), "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "processed"

    failed_payload = dict(success_payload, event_id="evt_008", status="FAILED")
    failed_body = json.dumps(failed_payload).encode()
    resp = client.post(
        "/payments/webhook/",
        content=failed_body,
        headers={"X-Signature": sign_body(failed_body), "Content-Type": "application/json"},
    )
    assert resp.status_code == 200

    booking_after = client.get(
        f"/bookings/{booking['id']}",
        headers=make_auth_header(create_access_token(user.id)),
    )
    assert booking_after.json()["status"] == "CONFIRMED"


def test_webhook_concurrent_duplicate_deliveries(client, db):
    from concurrent.futures import ThreadPoolExecutor

    from app.models.payment import Payment
    from app.models.webhook_event import WebhookEvent
    from app.schemas.payment import WebhookPayload
    from app.services.webhook_service import WebhookService
    from tests.conftest import TestSessionLocal

    user, booking = setup_booking(client, db)
    payload = {
        "event_id": "evt_concurrent_001",
        "provider_reference": "pay_concurrent_001",
        "booking_id": booking["id"],
        "status": "SUCCESS",
        "amount": "500.00",
        "occurred_at": datetime.now(UTC).isoformat(),
    }
    body = json.dumps(payload).encode()
    signature = sign_body(body)
    typed_payload = WebhookPayload(**payload)

    def deliver(_):
        session = TestSessionLocal()
        try:
            service = WebhookService(session)
            return service.process_webhook(body, signature, typed_payload)
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(deliver, range(5)))

    statuses = [r["status"] for r in results]
    assert statuses.count("processed") == 1
    assert statuses.count("duplicate") == 4

    verifier = TestSessionLocal()
    try:
        assert (
            verifier.query(WebhookEvent)
            .filter(WebhookEvent.event_id == "evt_concurrent_001")
            .count()
            == 1
        )
        assert (
            verifier.query(Payment)
            .filter(Payment.provider_reference == "pay_concurrent_001")
            .count()
            == 1
        )
    finally:
        verifier.close()

    booking_after = client.get(
        f"/bookings/{booking['id']}",
        headers=make_auth_header(create_access_token(user.id)),
    )
    assert booking_after.json()["status"] == "CONFIRMED"
    assert len(booking_after.json()["payments"]) == 1
