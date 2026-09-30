# EVE Healthcare - Diagnostic Test Booking Backend

Backend service for browsing diagnostic centres, booking tests, and simulated payments.

## Tech Stack

- Python 3.12, FastAPI, PostgreSQL 16
- SQLAlchemy 2.x + Alembic (migrations)
- Pydantic v2 (schemas), PyJWT (auth), bcrypt (passwords)
- Docker + docker-compose
- pytest (tests), ruff (linting)

## Quick Start (Docker)

```bash
docker compose up --build
```

This starts PostgreSQL + the API, runs migrations, seeds an admin user, and serves on `http://localhost:8000`.

**Swagger docs:** `http://localhost:8000/docs`

## Local Setup (without Docker)

```bash
# 1. Create databases
createdb eve_db
createdb eve_test_db

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy env file and update values
cp .env.example .env

# 4. Run migrations
alembic upgrade head

# 5. Seed admin user
python -m app.core.seed

# 6. Start server
uvicorn app.main:app --reload
```

## Running Tests

Tests require a running PostgreSQL instance. The test database URL is `DATABASE_URL_TEST` from `.env`.

```bash
# Create the test database first
createdb eve_test_db

# Run tests
python -m pytest tests/ -v
```

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/signup` | None | Create user account |
| POST | `/auth/login` | None | Get JWT token |
| GET | `/auth/me` | JWT | Current user profile |
| GET | `/centres` | Public | List centres with tests + prices |
| GET | `/centres/{id}` | Public | Centre detail |
| POST | `/centres` | Admin | Create centre |
| GET | `/tests` | Public | List test catalogue |
| POST | `/tests` | Admin | Create test |
| POST | `/centres/{id}/tests` | Admin | Attach test to centre with price |
| PATCH | `/centres/{id}/tests/{test_id}` | Admin | Update price/active |
| POST | `/bookings` | JWT | Create booking (PENDING) |
| GET | `/bookings` | JWT | List own bookings |
| GET | `/bookings/{id}` | JWT | Booking detail |
| POST | `/bookings/{id}/cancel` | JWT | Cancel booking |
| POST | `/payments/` | JWT | Simulate payment |
| POST | `/payments/webhook/` | HMAC | Provider status update |

## Example Usage

```bash
# Signup
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "full_name": "Test User", "password": "securepass123"}'

# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "securepass123"}'
# Returns: {"access_token": "<jwt>", "token_type": "bearer", "expires_in": 3600}

# Create booking
curl -X POST http://localhost:8000/bookings \
  -H "Authorization: Bearer <jwt>" \
  -H "Content-Type: application/json" \
  -d '{"centre_id": "<uuid>", "test_id": "<uuid>", "appointment_at": "2026-10-15T09:30:00Z"}'
# Returns: {"id": "<uuid>", "status": "PENDING", "amount": 850.00, ...}

# Simulate payment
curl -X POST http://localhost:8000/payments/ \
  -H "Authorization: Bearer <jwt>" \
  -H "Content-Type: application/json" \
  -d '{"booking_id": "<uuid>", "simulate": "SUCCESS"}'
# Returns: {"payment_id": "<uuid>", "status": "SUCCESS", "booking_status": "CONFIRMED"}
```

## Database Schema

```
users                    centre_tests                 webhook_events
-------                  ------------                 --------------
id (PK)                  id (PK)                      id (PK)
email (UNIQUE)           centre_id (FK)               event_id (UNIQUE)
full_name                test_id (FK)                 provider_reference
password_hash            price (NUMERIC 10,2)         payload (JSONB)
is_admin                 is_active                    received_at
created_at               created_at                   processed_at
                                                     outcome

diagnostic_centres       diagnostic_tests
-------------------      ----------------
id (PK)                  id (PK)
name                     name (UNIQUE)
city (INDEX)             description
address                  created_at
created_at

bookings
-------
id (PK)
user_id (FK)
centre_id (FK)
test_id (FK)
appointment_at
amount (NUMERIC 10,2)
status (ENUM: PENDING, CONFIRMED, FAILED, CANCELLED)
created_at
updated_at

payments
--------
id (PK)
booking_id (FK)
user_id (FK)
amount (NUMERIC 10,2)
status (ENUM: SUCCESS, FAILED)
provider_reference (UNIQUE)
idempotency_key
created_at
```

## Booking State Machine

```
PENDING ──→ CONFIRMED  (payment SUCCESS)
PENDING ──→ FAILED     (payment FAILED)
PENDING ──→ CANCELLED  (user cancels)
CONFIRMED ──→ CANCELLED (user cancels, no refund)
FAILED ──→ (terminal, no transitions)
CANCELLED ──→ (terminal, no transitions)
```

Centralised in `BookingService.transition()` - raises `ValueError` on illegal moves.

## Webhook Idempotency

1. Verify HMAC-SHA256 signature (constant-time compare) - 401 if invalid
2. Validate payload with Pydantic (`status` must be SUCCESS or FAILED) - 422 if invalid
3. Begin transaction
4. INSERT INTO webhook_events (event_id, ...) - UNIQUE violation means duplicate, return 200 "duplicate"
5. SELECT booking FOR UPDATE (row lock serialises concurrent deliveries)
6. Compare webhook amount with booking amount - mismatch returns 422 `AMOUNT_MISMATCH`, logs a warning, and rolls back (no state change, provider may retry)
7. Create/update payment record
8. Apply booking state transition via state machine (illegal moves, e.g. late SUCCESS on CANCELLED, are ignored and recorded as `IGNORED`)
9. COMMIT - return 200 "processed"

Handles: duplicates (sequential and concurrent), out-of-order events (FAILED after SUCCESS never downgrades), late webhooks on cancelled bookings, amount mismatches.

## Request IDs and Logging

- Every response carries an `X-Request-ID` header (client-supplied IDs are echoed back, otherwise a UUID is generated)
- Logs are structured JSON with `request_id`, method, path, status code and duration - useful for tracing a request across the stack
- Passwords, JWTs and the webhook secret are never logged

## Assumptions

- Money is in INR with 2 decimals, single currency
- No slot capacity or double-booking rules
- FAILED bookings are terminal (user creates a new booking)
- Cancelling a CONFIRMED booking does not trigger a refund
- Catalogue endpoints readable by any authenticated user; writes are admin only
- Webhook provider signs with HMAC secret + unique event_id per event
- All timestamps are ISO 8601 UTC

## What Would Improve with More Time

- Real payment gateway integration (Stripe/Razorpay)
- Refund flow for cancelled bookings
- Slot capacity management per centre
- Async webhook processing with Celery + Redis
- Rate limiting on auth endpoints
- CI pipeline (GitHub Actions)
- Observability (structured logging, metrics, tracing)
- Role-based access control beyond simple admin flag
