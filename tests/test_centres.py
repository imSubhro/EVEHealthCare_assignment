from app.core.security import create_access_token
from app.models.user import User
from tests.conftest import make_auth_header


def create_user(db, user_id, email, is_admin=False):
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


def admin_headers(db):
    admin = create_user(db, "admin-centre-id", "admin-centre@test.com", is_admin=True)
    return make_auth_header(create_access_token(admin.id, is_admin=True))


def user_headers(db):
    user = create_user(db, "user-centre-id", "user-centre@test.com")
    return make_auth_header(create_access_token(user.id))


def test_admin_create_centre(client, db):
    resp = client.post(
        "/centres",
        json={"name": "Alpha Labs", "city": "Pune", "address": "1 MG Road"},
        headers=admin_headers(db),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Alpha Labs"
    assert data["city"] == "Pune"


def test_non_admin_create_centre_forbidden(client, db):
    resp = client.post(
        "/centres",
        json={"name": "Beta Labs", "city": "Pune", "address": "2 MG Road"},
        headers=user_headers(db),
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "FORBIDDEN"


def test_duplicate_centre_rejected(client, db):
    h = admin_headers(db)
    body = {"name": "Gamma Labs", "city": "Delhi", "address": "3 MG Road"}
    client.post("/centres", json=body, headers=h)
    resp = client.post("/centres", json=body, headers=h)
    assert resp.status_code == 409


def test_admin_create_test_and_attach_price(client, db):
    h = admin_headers(db)
    centre_resp = client.post(
        "/centres",
        json={"name": "Delta Labs", "city": "Mumbai", "address": "4 MG Road"},
        headers=h,
    )
    centre_id = centre_resp.json()["id"]

    test_resp = client.post(
        "/tests",
        json={"name": "Sugar Test", "description": "Blood sugar"},
        headers=h,
    )
    assert test_resp.status_code == 201
    test_id = test_resp.json()["id"]

    attach_resp = client.post(
        f"/centres/{centre_id}/tests",
        json={"test_id": test_id, "price": 450.50},
        headers=h,
    )
    assert attach_resp.status_code == 201
    assert float(attach_resp.json()["price"]) == 450.50
    assert attach_resp.json()["is_active"] is True

    dup_resp = client.post(
        f"/centres/{centre_id}/tests",
        json={"test_id": test_id, "price": 500.00},
        headers=h,
    )
    assert dup_resp.status_code == 409


def test_non_admin_attach_forbidden(client, db):
    h = admin_headers(db)
    centre_resp = client.post(
        "/centres",
        json={"name": "Epsilon Labs", "city": "Chennai", "address": "5 MG Road"},
        headers=h,
    )
    test_resp = client.post(
        "/tests",
        json={"name": "Chol Test", "description": "Cholesterol"},
        headers=h,
    )
    resp = client.post(
        f"/centres/{centre_resp.json()['id']}/tests",
        json={"test_id": test_resp.json()["id"], "price": 300.00},
        headers=user_headers(db),
    )
    assert resp.status_code == 403


def test_invalid_price_rejected(client, db):
    h = admin_headers(db)
    centre_resp = client.post(
        "/centres",
        json={"name": "Zeta Labs", "city": "Kolkata", "address": "6 MG Road"},
        headers=h,
    )
    test_resp = client.post(
        "/tests",
        json={"name": "Vit D Test", "description": "Vitamin D"},
        headers=h,
    )
    resp = client.post(
        f"/centres/{centre_resp.json()['id']}/tests",
        json={"test_id": test_resp.json()["id"], "price": -10},
        headers=h,
    )
    assert resp.status_code == 422


def test_update_price_and_active_flag(client, db):
    h = admin_headers(db)
    centre_resp = client.post(
        "/centres",
        json={"name": "Eta Labs", "city": "Hyderabad", "address": "7 MG Road"},
        headers=h,
    )
    centre_id = centre_resp.json()["id"]
    test_resp = client.post(
        "/tests",
        json={"name": "Liver Test", "description": "LFT panel"},
        headers=h,
    )
    test_id = test_resp.json()["id"]
    client.post(
        f"/centres/{centre_id}/tests",
        json={"test_id": test_id, "price": 600.00},
        headers=h,
    )

    resp = client.patch(
        f"/centres/{centre_id}/tests/{test_id}",
        json={"price": 700.00, "is_active": False},
        headers=h,
    )
    assert resp.status_code == 200
    assert float(resp.json()["price"]) == 700.00
    assert resp.json()["is_active"] is False

    resp_non_admin = client.patch(
        f"/centres/{centre_id}/tests/{test_id}",
        json={"price": 100.00},
        headers=user_headers(db),
    )
    assert resp_non_admin.status_code == 403


def test_list_centres_pagination_and_filters(client, db):
    h = admin_headers(db)
    client.post(
        "/centres",
        json={"name": "Theta Labs", "city": "Pune", "address": "8 MG Road"},
        headers=h,
    )
    client.post(
        "/centres",
        json={"name": "Iota Labs", "city": "Delhi", "address": "9 MG Road"},
        headers=h,
    )
    centre_resp = client.post(
        "/centres",
        json={"name": "Kappa Labs", "city": "Mumbai", "address": "10 MG Road"},
        headers=h,
    )
    centre_id = centre_resp.json()["id"]
    test_resp = client.post(
        "/tests",
        json={"name": "Urine Test", "description": "Routine urinalysis"},
        headers=h,
    )
    client.post(
        f"/centres/{centre_id}/tests",
        json={"test_id": test_resp.json()["id"], "price": 200.00},
        headers=h,
    )

    page1 = client.get("/centres?limit=2&offset=0")
    assert page1.status_code == 200
    assert len(page1.json()) == 2

    page2 = client.get("/centres?limit=2&offset=2")
    assert len(page2.json()) == 1

    by_city = client.get("/centres?city=pune")
    assert len(by_city.json()) == 1
    assert by_city.json()[0]["city"] == "Pune"

    by_test = client.get("/centres?test_name=Urine")
    assert len(by_test.json()) == 1
    assert by_test.json()[0]["id"] == centre_id

    empty = client.get("/centres?city=Nowhereville")
    assert empty.json() == []


def test_list_tests_and_pagination(client, db):
    h = admin_headers(db)
    client.post("/tests", json={"name": "T1 Panel", "description": "d"}, headers=h)
    client.post("/tests", json={"name": "T2 Panel", "description": "d"}, headers=h)

    resp = client.get("/tests?limit=1&offset=0")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp_all = client.get("/tests?limit=100")
    assert len(resp_all.json()) >= 2


def test_get_unknown_centre_404(client):
    resp = client.get("/centres/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "CENTRE_NOT_FOUND"
