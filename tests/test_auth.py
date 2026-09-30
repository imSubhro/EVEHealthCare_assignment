def test_signup_success(client):
    resp = client.post(
        "/auth/signup",
        json={
            "email": "test@example.com",
            "full_name": "Test User",
            "password": "securepass123",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "test@example.com"
    assert "id" in data


def test_signup_duplicate_email(client):
    client.post(
        "/auth/signup",
        json={
            "email": "dup@example.com",
            "full_name": "User 1",
            "password": "securepass123",
        },
    )
    resp = client.post(
        "/auth/signup",
        json={
            "email": "dup@example.com",
            "full_name": "User 2",
            "password": "securepass123",
        },
    )
    assert resp.status_code == 409


def test_signup_weak_password(client):
    resp = client.post(
        "/auth/signup",
        json={"email": "weak@example.com", "full_name": "Weak", "password": "short"},
    )
    assert resp.status_code == 422


def test_login_success(client):
    client.post(
        "/auth/signup",
        json={
            "email": "login@example.com",
            "full_name": "Login",
            "password": "securepass123",
        },
    )
    resp = client.post(
        "/auth/login",
        json={"email": "login@example.com", "password": "securepass123"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_wrong_password(client):
    client.post(
        "/auth/signup",
        json={
            "email": "wrong@example.com",
            "full_name": "Wrong",
            "password": "securepass123",
        },
    )
    resp = client.post(
        "/auth/login",
        json={"email": "wrong@example.com", "password": "wrongpassword"},
    )
    assert resp.status_code == 401


def test_protected_route_no_token(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_protected_route_invalid_token(client):
    resp = client.get("/auth/me", headers={"Authorization": "Bearer invalidtoken"})
    assert resp.status_code == 401


def test_protected_route_expired_token(client):
    import jwt
    from datetime import UTC, datetime, timedelta

    from app.core.config import get_settings

    settings = get_settings()
    now = datetime.now(UTC)
    expired = jwt.encode(
        {
            "sub": "user-test-id",
            "is_admin": False,
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "TOKEN_EXPIRED"


def test_signup_invalid_email(client):
    resp = client.post(
        "/auth/signup",
        json={
            "email": "not-an-email",
            "full_name": "Bad Email",
            "password": "securepass123",
        },
    )
    assert resp.status_code == 422
