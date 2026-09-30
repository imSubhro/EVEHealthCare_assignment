from datetime import UTC, datetime, timedelta

from app.core.security import create_access_token
from app.models.user import User
from tests.conftest import make_auth_header


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


def test_payment_success(client, db):
    user, booking = setup_booking(client, db)
    token = create_access_token(user.id)
    resp = client.post(
        "/payments/",
        json={"booking_id": booking["id"], "simulate": "SUCCESS"},
        headers=make_auth_header(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["booking_status"] == "CONFIRMED"


def test_payment_failed(client, db):
    user, booking = setup_booking(client, db)
    token = create_access_token(user.id)
    resp = client.post(
        "/payments/",
        json={"booking_id": booking["id"], "simulate": "FAILED"},
        headers=make_auth_header(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "FAILED"
    assert data["booking_status"] == "FAILED"


def test_pay_non_pending_booking(client, db):
    user, booking = setup_booking(client, db)
    token = create_access_token(user.id)

    client.post(
        "/payments/",
        json={"booking_id": booking["id"], "simulate": "SUCCESS"},
        headers=make_auth_header(token),
    )

    resp = client.post(
        "/payments/",
        json={"booking_id": booking["id"], "simulate": "SUCCESS"},
        headers=make_auth_header(token),
    )
    assert resp.status_code == 409


def test_pay_other_users_booking(client, db):
    user, booking = setup_booking(client, db)
    other_user = create_test_user(db, user_id="other-user", email="other@test.com")
    other_token = create_access_token(other_user.id)
    resp = client.post(
        "/payments/",
        json={"booking_id": booking["id"], "simulate": "SUCCESS"},
        headers=make_auth_header(other_token),
    )
    assert resp.status_code == 404


def test_payment_idempotency_key_reuse(client, db):
    user, booking = setup_booking(client, db)
    token = create_access_token(user.id)

    resp1 = client.post(
        "/payments/",
        json={"booking_id": booking["id"], "simulate": "SUCCESS"},
        headers={**make_auth_header(token), "Idempotency-Key": "idem-123"},
    )
    assert resp1.status_code == 201

    resp2 = client.post(
        "/payments/",
        json={"booking_id": booking["id"], "simulate": "SUCCESS"},
        headers={**make_auth_header(token), "Idempotency-Key": "idem-123"},
    )
    assert resp2.status_code == 201
    assert resp2.json()["payment_id"] == resp1.json()["payment_id"]
