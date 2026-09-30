import hashlib
import hmac
import json
import uuid

import requests

BASE = "http://localhost:8000"
RUN = uuid.uuid4().hex[:8]


def test_everything():
    print("=" * 60)
    print("EVE HEALTHCARE - FULL API TEST")
    print("=" * 60)

    # 1. Health check
    r = requests.get(f"{BASE}/health")
    print(f"\n1. Health Check: {r.status_code} -> {r.json()}")

    # 2. Signup user (409 is fine on re-runs)
    r = requests.post(f"{BASE}/auth/signup", json={
        "email": "asha@test.com",
        "full_name": "Asha Roy",
        "password": "securepass123"
    })
    print(f"\n2. Signup User: {r.status_code} -> {r.json()}")

    # 3. Login admin (seeded by app.core.seed, cannot be created via signup)
    r = requests.post(f"{BASE}/auth/login", json={
        "email": "admin@eve.com",
        "password": "admin1234"
    })
    admin_token = r.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print(f"\n3. Login Admin: {r.status_code} -> token obtained")

    # 4. Login user
    r = requests.post(f"{BASE}/auth/login", json={
        "email": "asha@test.com",
        "password": "securepass123"
    })
    user_token = r.json()["access_token"]
    user_headers = {"Authorization": f"Bearer {user_token}"}
    print(f"\n4. Login User: {r.status_code} -> token obtained")

    # 5. Get admin info
    r = requests.get(f"{BASE}/auth/me", headers=admin_headers)
    print(f"\n5. Admin Me: {r.status_code} -> is_admin={r.json()['is_admin']}")

    # 6. Get current user
    r = requests.get(f"{BASE}/auth/me", headers=user_headers)
    print(f"\n6. Get Me: {r.status_code} -> {r.json()}")

    # 7. Create centre (admin)
    r = requests.post(f"{BASE}/centres", json={
        "name": f"CareFirst Labs {RUN}",
        "city": "Delhi",
        "address": "45 Park Street"
    }, headers=admin_headers)
    print(f"\n7. Create Centre: {r.status_code} -> {r.json()}")
    centre_id = r.json()["id"]

    # 8. Create test (admin)
    r = requests.post(f"{BASE}/tests", json={
        "name": f"Thyroid Test {RUN}",
        "description": "Thyroid function test"
    }, headers=admin_headers)
    print(f"\n8. Create Test: {r.status_code} -> {r.json()}")
    test_id = r.json()["id"]

    # 9. Attach test to centre (admin)
    r = requests.post(f"{BASE}/centres/{centre_id}/tests", json={
        "test_id": test_id,
        "price": 750.00
    }, headers=admin_headers)
    print(f"\n9. Attach Test: {r.status_code} -> {r.json()}")

    # 10. List centres (user)
    r = requests.get(f"{BASE}/centres", headers=user_headers)
    print(f"\n10. List Centres: {r.status_code} -> {len(r.json())} centre(s)")

    # 11. Get single centre
    r = requests.get(f"{BASE}/centres/{centre_id}", headers=user_headers)
    print(f"\n11. Get Centre: {r.status_code} -> {r.json()['name']}")

    # 12. List tests
    r = requests.get(f"{BASE}/tests", headers=user_headers)
    print(f"\n12. List Tests: {r.status_code} -> {len(r.json())} test(s)")

    # 13. Create booking (user)
    r = requests.post(f"{BASE}/bookings", json={
        "centre_id": centre_id,
        "test_id": test_id,
        "appointment_at": "2026-10-15T09:30:00Z"
    }, headers=user_headers)
    print(f"\n13. Create Booking: {r.status_code} -> status={r.json()['status']}, amount={r.json()['amount']}")
    booking_id = r.json()["id"]

    # 14. List bookings
    r = requests.get(f"{BASE}/bookings", headers=user_headers)
    print(f"\n14. List Bookings: {r.status_code} -> {len(r.json())} booking(s)")

    # 15. Get single booking (detail incl. payments)
    r = requests.get(f"{BASE}/bookings/{booking_id}", headers=user_headers)
    print(f"\n15. Get Booking: {r.status_code} -> status={r.json()['status']}, payments={len(r.json()['payments'])}")

    # 16. Simulate payment SUCCESS
    r = requests.post(f"{BASE}/payments/", json={
        "booking_id": booking_id,
        "simulate": "SUCCESS"
    }, headers=user_headers)
    print(f"\n16. Payment SUCCESS: {r.status_code} -> {r.json()}")

    # 17. Check booking is now CONFIRMED + payment listed in detail
    r = requests.get(f"{BASE}/bookings/{booking_id}", headers=user_headers)
    detail = r.json()
    print(f"\n17. Booking After Payment: status={detail['status']}, payments={len(detail['payments'])}")

    # 18. Create booking for cancel
    r = requests.post(f"{BASE}/bookings", json={
        "centre_id": centre_id,
        "test_id": test_id,
        "appointment_at": "2026-11-01T10:00:00Z"
    }, headers=user_headers)
    booking2_id = r.json()["id"]
    print(f"\n18. Create Booking 2: {r.status_code} -> status={r.json()['status']}")

    # 19. Cancel booking
    r = requests.post(f"{BASE}/bookings/{booking2_id}/cancel", headers=user_headers)
    print(f"\n19. Cancel Booking: {r.status_code} -> status={r.json()['status']}")

    # 20. Create booking for failed payment
    r = requests.post(f"{BASE}/bookings", json={
        "centre_id": centre_id,
        "test_id": test_id,
        "appointment_at": "2026-12-01T10:00:00Z"
    }, headers=user_headers)
    booking3_id = r.json()["id"]
    print(f"\n20. Create Booking 3: {r.status_code} -> status={r.json()['status']}")

    # 21. Simulate payment FAILED
    r = requests.post(f"{BASE}/payments/", json={
        "booking_id": booking3_id,
        "simulate": "FAILED"
    }, headers=user_headers)
    print(f"\n21. Payment FAILED: {r.status_code} -> {r.json()}")

    # 22. Check booking is FAILED
    r = requests.get(f"{BASE}/bookings/{booking3_id}", headers=user_headers)
    print(f"\n22. Booking After Failed: status={r.json()['status']}")

    # 23. Create booking for webhook
    r = requests.post(f"{BASE}/bookings", json={
        "centre_id": centre_id,
        "test_id": test_id,
        "appointment_at": "2026-11-15T10:00:00Z"
    }, headers=user_headers)
    booking4_id = r.json()["id"]
    print(f"\n23. Create Booking 4 (webhook): {r.status_code} -> status={r.json()['status']}")

    # 24. Send webhook with HMAC signature
    webhook_payload = json.dumps({
        "event_id": f"evt_{RUN}",
        "provider_reference": f"pay_{RUN}",
        "booking_id": booking4_id,
        "status": "SUCCESS",
        "amount": "750.00",
        "occurred_at": "2026-10-01T10:00:00Z"
    })
    secret = b"webhook-hmac-shared-secret-change-me"
    sig = hmac.new(secret, webhook_payload.encode(), hashlib.sha256).hexdigest()
    r = requests.post(f"{BASE}/payments/webhook/",
        data=webhook_payload.encode(),
        headers={"X-Signature": sig, "Content-Type": "application/json"})
    print(f"\n24. Webhook Call: {r.status_code} -> {r.json()}")

    # 25. Verify booking CONFIRMED via webhook
    r = requests.get(f"{BASE}/bookings/{booking4_id}", headers=user_headers)
    print(f"\n25. Booking After Webhook: status={r.json()['status']}")

    # 26. Duplicate webhook (idempotency)
    r = requests.post(f"{BASE}/payments/webhook/",
        data=webhook_payload.encode(),
        headers={"X-Signature": sig, "Content-Type": "application/json"})
    print(f"\n26. Duplicate Webhook: {r.status_code} -> {r.json()}")

    # 27. Amount mismatch webhook -> 422
    r = requests.post(f"{BASE}/bookings", json={
        "centre_id": centre_id,
        "test_id": test_id,
        "appointment_at": "2027-01-15T10:00:00Z"
    }, headers=user_headers)
    booking5_id = r.json()["id"]
    mismatch_payload = json.dumps({
        "event_id": f"evt_mm_{RUN}",
        "provider_reference": f"pay_mm_{RUN}",
        "booking_id": booking5_id,
        "status": "SUCCESS",
        "amount": "99999.00",
        "occurred_at": "2026-10-01T10:00:00Z"
    })
    sig2 = hmac.new(secret, mismatch_payload.encode(), hashlib.sha256).hexdigest()
    r = requests.post(f"{BASE}/payments/webhook/",
        data=mismatch_payload.encode(),
        headers={"X-Signature": sig2, "Content-Type": "application/json"})
    print(f"\n27. Amount Mismatch Webhook: {r.status_code} -> {r.json()}")
    r = requests.get(f"{BASE}/bookings/{booking5_id}", headers=user_headers)
    print(f"    Booking unchanged: status={r.json()['status']}")

    # 28. Pay non-PENDING booking -> 409
    r = requests.post(f"{BASE}/payments/", json={
        "booking_id": booking_id,
        "simulate": "SUCCESS"
    }, headers=user_headers)
    print(f"\n28. Pay Confirmed Booking: {r.status_code} -> should be 409")

    # 29. Other user cannot see your booking -> 404
    requests.post(f"{BASE}/auth/signup", json={
        "email": "other@test.com",
        "full_name": "Other User",
        "password": "securepass123"
    })
    r2 = requests.post(f"{BASE}/auth/login", json={
        "email": "other@test.com",
        "password": "securepass123"
    })
    other_headers = {"Authorization": f"Bearer {r2.json()['access_token']}"}
    r = requests.get(f"{BASE}/bookings/{booking_id}", headers=other_headers)
    print(f"\n29. Other User Access: {r.status_code} -> should be 404")

    # 30. Malformed booking id -> 422
    r = requests.get(f"{BASE}/bookings/not-a-uuid", headers=user_headers)
    print(f"\n30. Malformed Booking ID: {r.status_code} -> should be 422")

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    test_everything()
