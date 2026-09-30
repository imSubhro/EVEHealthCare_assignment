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


def test_create_booking(client, db):
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
    token = create_access_token(user.id)
    resp = client.post(
        "/bookings",
        json={
            "centre_id": centre_id,
            "test_id": test_id,
            "appointment_at": future_date,
        },
        headers=make_auth_header(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "PENDING"
    assert float(data["amount"]) == 500.00


def test_create_booking_past_date(client, db):
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

    past_date = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    token = create_access_token(user.id)
    resp = client.post(
        "/bookings",
        json={
            "centre_id": centre_id,
            "test_id": test_id,
            "appointment_at": past_date,
        },
        headers=make_auth_header(token),
    )
    assert resp.status_code == 422


def test_cancel_booking(client, db):
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
    token = create_access_token(user.id)
    booking_resp = client.post(
        "/bookings",
        json={
            "centre_id": centre_id,
            "test_id": test_id,
            "appointment_at": future_date,
        },
        headers=make_auth_header(token),
    )
    booking_id = booking_resp.json()["id"]

    cancel_resp = client.post(
        f"/bookings/{booking_id}/cancel",
        headers=make_auth_header(token),
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "CANCELLED"


def test_other_user_booking_blocked(client, db):
    admin = create_admin_user(db)
    user1 = create_test_user(db, user_id="user-1", email="u1@test.com")
    user2 = create_test_user(db, user_id="user-2", email="u2@test.com")

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
        headers=make_auth_header(create_access_token(user1.id)),
    )
    booking_id = booking_resp.json()["id"]

    resp = client.get(
        f"/bookings/{booking_id}",
        headers=make_auth_header(create_access_token(user2.id)),
    )
    assert resp.status_code == 404


def test_malformed_booking_id_rejected(client, db):
    create_test_user(db)
    token = create_access_token("user-test-id")
    resp = client.get(
        "/bookings/not-a-uuid", headers=make_auth_header(token)
    )
    assert resp.status_code == 422

    resp = client.post(
        "/bookings/not-a-uuid/cancel", headers=make_auth_header(token)
    )
    assert resp.status_code == 422

    resp = client.post(
        "/payments/",
        json={"booking_id": "not-a-uuid", "simulate": "SUCCESS"},
        headers=make_auth_header(token),
    )
    assert resp.status_code == 422


def test_booking_detail_includes_payments(client, db):
    admin = create_admin_user(db)
    user = create_test_user(db)

    centre_resp = client.post(
        "/centres",
        json={"name": "Detail Centre", "city": "Pune", "address": "1 Road"},
        headers=make_auth_header(create_access_token(admin.id, is_admin=True)),
    )
    test_resp = client.post(
        "/tests",
        json={"name": "Detail Test", "description": "d"},
        headers=make_auth_header(create_access_token(admin.id, is_admin=True)),
    )
    client.post(
        f"/centres/{centre_resp.json()['id']}/tests",
        json={"test_id": test_resp.json()["id"], "price": 250.00},
        headers=make_auth_header(create_access_token(admin.id, is_admin=True)),
    )

    token = create_access_token(user.id)
    booking_resp = client.post(
        "/bookings",
        json={
            "centre_id": centre_resp.json()["id"],
            "test_id": test_resp.json()["id"],
            "appointment_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
        },
        headers=make_auth_header(token),
    )
    booking_id = booking_resp.json()["id"]

    before = client.get(
        f"/bookings/{booking_id}", headers=make_auth_header(token)
    )
    assert before.status_code == 200
    assert before.json()["payments"] == []

    pay = client.post(
        "/payments/",
        json={"booking_id": booking_id, "simulate": "SUCCESS"},
        headers=make_auth_header(token),
    )
    assert pay.status_code == 201

    after = client.get(f"/bookings/{booking_id}", headers=make_auth_header(token))
    data = after.json()
    assert data["status"] == "CONFIRMED"
    assert len(data["payments"]) == 1
    assert data["payments"][0]["status"] == "SUCCESS"
    assert float(data["payments"][0]["amount"]) == 250.00
