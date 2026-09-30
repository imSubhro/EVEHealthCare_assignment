# Product Requirements & Design Document
## Diagnostic Test Booking & Simulated Payments Backend

**EVE Healthcare - SDE Intern Backend Engineering Assignment**

| | |
|---|---|
| Document type | PRD + technical design (build-from-scratch brief) |
| Audience | Senior backend developer |
| Version / date | v1.0 - 29 September 2026 |
| Estimated effort | 3-4 hours for core scope; bonus items optional |
| Recommended stack | Python 3.12, FastAPI, PostgreSQL 16, SQLAlchemy 2.x, Alembic, Pydantic v2, PyJWT, pytest, Docker |

> EVE says they care more about engineering thinking than feature count. A small, clean, well-tested solution with a clear README beats a large messy one. Optimise for that.

---

## 1. Purpose and Goals

Build a small backend service where authenticated users can browse diagnostic centres and the tests they offer, book a test, pay through a **simulated** payment service, and receive payment status updates through an **idempotent webhook**. No real payment gateway is integrated.

### Goals
- Clean, layered, maintainable code (20% of grading).
- Well-designed REST API with correct status codes and validation (20%).
- Correct relational data model with constraints and indexes (15%).
- Robust edge-case handling, especially webhook idempotency and booking state integrity (15%).
- Meaningful automated tests (10%) and a clear README and Git history (10%).
- Selected bonus engineering (10%): Docker, OpenAPI, pagination, structured logging, etc.

### Non-goals
- Real payment gateway, refunds, invoicing, notifications (email/SMS).
- Any frontend / UI.
- Slot inventory or capacity management per centre.
- Role hierarchies beyond a simple admin flag.

---

## 2. Scope Summary

| Area | Requirement | Priority |
|---|---|---|
| Authentication | Signup, login, JWT access tokens, request validation | Must |
| Centres and tests | Create and retrieve centres, tests, per-centre test prices | Must |
| Bookings | Authenticated users create, list, view, cancel own bookings | Must |
| Simulated payment | `POST /payments/` returns SUCCESS or FAILED and updates the booking | Must |
| Payment webhook | `POST /payments/webhook/` idempotent, safe under retries and duplicates | Must |
| Edge cases | Invalid input, bad IDs, failed payments, unauthorized access, duplicates | Must |
| Tests | Unit and integration tests, emphasis on webhook and state transitions | Must (graded) |
| Docs | README, Swagger/OpenAPI, schema description, assumptions | Must (graded) |
| Bonus | Docker + compose, pagination, structured logging, rate limiting, Redis, Celery, webhook retries | Should / Could |

---

## 3. Technology Choices

| Concern | Choice | Reason |
|---|---|---|
| Framework | FastAPI | Pydantic validation, automatic Swagger/OpenAPI, dependency injection for auth and DB sessions |
| Database | PostgreSQL 16 | Preferred by EVE; row locks, JSONB, unique constraints for idempotency |
| ORM / migrations | SQLAlchemy 2.x + Alembic | Explicit schema, versioned migrations |
| Auth | PyJWT + bcrypt | Standard JWT bearer tokens, salted password hashing |
| Config | pydantic-settings (`.env`) | 12-factor configuration, no secrets in code |
| Testing | pytest + httpx TestClient | API-level tests against a real Postgres test DB |
| Packaging | Docker + docker-compose | One-command local run (api + postgres) |

Django or Flask is acceptable per the assignment, but this document assumes FastAPI. Pick one and stay consistent.

---

## 4. Architecture and Project Structure

Layered design: **routers** (HTTP only) call **services** (business rules, transactions), which use **models/repositories** (DB access). Business rules must not live in route handlers.

```
eve-backend/
  app/
    main.py                 # app factory, router registration, exception handlers
    core/
      config.py             # settings from env
      security.py           # password hashing, JWT create/verify, webhook HMAC
      logging.py            # structured (JSON) logging setup
    db/
      session.py            # engine, SessionLocal, get_db dependency
      base.py               # declarative base
    models/                 # user, centre, test, centre_test, booking, payment, webhook_event
    schemas/                # Pydantic request/response models
    api/
      deps.py               # get_current_user, require_admin
      routes/               # auth.py, centres.py, tests.py, bookings.py, payments.py
    services/               # auth_service, booking_service, payment_service, webhook_service
  alembic/                  # migrations
  tests/                    # conftest.py, test_auth.py, test_bookings.py, test_payments.py, test_webhook.py
  Dockerfile
  docker-compose.yml
  requirements.txt
  .env.example
  README.md
```

---

## 5. Functional Requirements

### 5.1 Authentication
- **Signup**: email (unique, valid format, case-insensitive), full name, password (min 8 chars). Store only a bcrypt hash. Return 201 with user id and email, never the hash.
- **Login**: email + password, returns a JWT bearer token (HS256) with `sub` (user id), `exp` (default 60 min), `iat`. Invalid credentials return 401 with a generic message.
- **Protected routes** require `Authorization: Bearer <token>`. Missing, malformed or expired token returns 401.
- **Admin**: `users` has an `is_admin` flag. Centre and test management endpoints require admin. Provide a seed script or env-driven bootstrap admin so reviewers can test.

### 5.2 Diagnostic Centres and Tests
- A **centre** has a name and location (city plus address). A **test** is a catalogue entry (name, description). A **centre-test** link carries the **price** for that test at that centre, so the same test can cost different amounts at different centres.
- Read endpoints: list centres with their tests and prices, get one centre, list tests. Support pagination (limit/offset) and simple filters (location, test name).
- Admin write endpoints: create centre, create test, attach a test to a centre with a price, update price.
- Price is a positive decimal `NUMERIC(10,2)`. Never use floats for money.

### 5.3 Booking System
- An authenticated user books a test at a specific centre for a future appointment date/time.
- The booking must reference a valid centre-test combination. If the centre does not offer the test, return 422 (or 404 for unknown IDs).
- **Amount is snapshotted** from the current centre-test price at creation time, so later price changes do not alter existing bookings.
- Appointment must be in the future (timezone-aware, stored in UTC).
- New bookings start as **PENDING**.
- Users can list and view only their own bookings, and cancel per the state machine in section 7.

### 5.4 Simulated Payment Service
- **`POST /payments/`** body: `booking_id` and optional `simulate` (`SUCCESS` or `FAILED`). If `simulate` is omitted, choose randomly using a configurable success rate (env var, default 80%). The override keeps tests deterministic.
- Only the booking owner may pay. Booking must be PENDING, otherwise 409.
- Create a payment row with `amount = booking.amount` and a generated `provider_reference`. Set payment status to SUCCESS or FAILED and update the booking in the **same DB transaction**: SUCCESS moves the booking to CONFIRMED, FAILED moves it to FAILED.
- Support an optional `Idempotency-Key` header so a client retry does not create a second payment (bonus, recommended).

### 5.5 Payment Webhook
- **`POST /payments/webhook/`** is called by the simulated provider, not end users, so it does not use JWT. It is authenticated with an HMAC-SHA256 signature in the `X-Signature` header, computed over the raw body with a shared secret (`WEBHOOK_SECRET`). Invalid signature returns 401.
- Payload: `event_id` (unique per provider event), `provider_reference`, `booking_id`, `status` (SUCCESS or FAILED), `amount`, `occurred_at`.
- **Idempotent by design** (see section 7). The same `event_id` delivered any number of times produces exactly one state change and no duplicate rows.
- Return 200 for a valid, already-processed duplicate so the provider stops retrying. Return 4xx only for genuinely invalid requests.

---

## 6. Data Model

All primary keys are UUIDs (or BIGINT identity, pick one). All timestamps are `TIMESTAMPTZ` in UTC. Money is `NUMERIC(10,2)`.

| Table | Columns | Constraints / indexes |
|---|---|---|
| `users` | id, email, full_name, password_hash, is_admin (default false), created_at | UNIQUE(lower(email)) |
| `diagnostic_centres` | id, name, city, address, created_at | INDEX(city); UNIQUE(name, city) |
| `diagnostic_tests` | id, name, description, created_at | UNIQUE(name) |
| `centre_tests` | id, centre_id FK, test_id FK, price, is_active | UNIQUE(centre_id, test_id); CHECK(price > 0) |
| `bookings` | id, user_id FK, centre_id FK, test_id FK, appointment_at, amount, status ENUM(PENDING, CONFIRMED, FAILED, CANCELLED), created_at, updated_at | INDEX(user_id, created_at DESC); INDEX(status); CHECK(amount > 0) |
| `payments` | id, booking_id FK, user_id FK, amount, status ENUM(SUCCESS, FAILED), provider_reference, idempotency_key NULL, created_at | UNIQUE(provider_reference); UNIQUE(user_id, idempotency_key) where key not null; partial UNIQUE(booking_id) WHERE status = 'SUCCESS' |
| `webhook_events` | id, event_id, provider_reference, payload JSONB, received_at, processed_at, outcome | **UNIQUE(event_id)** - the idempotency guard |

**Relationships:** user 1-N bookings; centre N-M test through `centre_tests`; booking N-1 centre and test; booking 1-N payments (a failed attempt followed by a later success is only possible if retries are enabled; by default at most one SUCCESS payment per booking, enforced by the partial unique index).

---

## 7. Booking State Machine and Webhook Idempotency

### 7.1 Booking state machine

| From | To | Trigger | Allowed? |
|---|---|---|---|
| PENDING | CONFIRMED | Payment SUCCESS (API or webhook) | Yes |
| PENDING | FAILED | Payment FAILED (API or webhook) | Yes |
| PENDING | CANCELLED | User cancels | Yes |
| CONFIRMED | CANCELLED | User cancels (no refund flow in scope) | Yes (document as assumption) |
| CONFIRMED | FAILED / PENDING | Any | No |
| FAILED | any | Any | No - terminal; user creates a new booking |
| CANCELLED | any | Any, including a late SUCCESS webhook | No - ignore, log a warning, record outcome |

Centralise transitions in one function (e.g. `BookingService.transition(booking, new_status)`) that raises a domain error on an illegal move. Never set status directly in route handlers.

### 7.2 Webhook processing algorithm

```
1. Read RAW request body. Verify HMAC-SHA256 with WEBHOOK_SECRET (constant-time compare).
   Bad signature -> 401.
2. Validate payload with Pydantic. Invalid -> 422.
3. BEGIN transaction.
4. INSERT INTO webhook_events (event_id, payload, ...).
   - On UNIQUE(event_id) violation -> ROLLBACK, return 200 {"status": "duplicate"}.
5. SELECT booking ... FOR UPDATE   (row lock; serialises concurrent deliveries).
   - Not found -> record outcome=UNKNOWN_BOOKING, return 404.
6. Look up payment by provider_reference:
   - none   -> create payment with webhook status
   - exists -> update only if the transition is legal (never downgrade SUCCESS)
7. Apply booking transition via the state machine.
   - Illegal transition (e.g. booking CANCELLED) -> keep state, outcome=IGNORED, log warning.
8. Set webhook_events.processed_at / outcome. COMMIT. Return 200.
```

**Why this works:** the `UNIQUE(event_id)` insert makes duplicate detection atomic even under concurrent deliveries; the row lock prevents two different events for the same booking racing; the partial unique index on SUCCESS payments is a last-line database guarantee against duplicate successful payments.

Also handle **out-of-order** events (a FAILED arriving after SUCCESS for the same payment must not overwrite SUCCESS) and **amount mismatch** (webhook amount differs from booking amount: reject and log).

---

## 8. API Specification

The payments routes must remain exactly `/payments/` and `/payments/webhook/` as specified by EVE. All responses are JSON. Use a consistent error envelope, e.g. `{"detail": "message", "code": "BOOKING_NOT_FOUND"}`.

| Method | Path | Auth | Description | Success |
|---|---|---|---|---|
| POST | `/auth/signup` | None | Create user account | 201 |
| POST | `/auth/login` | None | Return JWT access token | 200 |
| GET | `/auth/me` | JWT | Current user profile (optional) | 200 |
| GET | `/centres` | JWT or public | List centres with tests and prices; filters + pagination | 200 |
| GET | `/centres/{id}` | JWT or public | Centre detail | 200 |
| POST | `/centres` | Admin | Create centre | 201 |
| GET | `/tests` | JWT or public | List test catalogue | 200 |
| POST | `/tests` | Admin | Create test | 201 |
| POST | `/centres/{id}/tests` | Admin | Attach test to centre with price | 201 |
| PATCH | `/centres/{id}/tests/{test_id}` | Admin | Update price / active flag | 200 |
| POST | `/bookings` | JWT | Create booking (PENDING) | 201 |
| GET | `/bookings` | JWT | List own bookings; pagination, status filter | 200 |
| GET | `/bookings/{id}` | JWT (owner) | Booking detail incl. payment | 200 |
| POST | `/bookings/{id}/cancel` | JWT (owner) | Cancel booking | 200 |
| POST | `/payments/` | JWT (owner) | Simulate payment for a booking | 201 |
| POST | `/payments/webhook/` | HMAC signature | Provider status update (idempotent) | 200 |

### Example requests

```http
POST /auth/signup
{ "email": "asha@example.com", "full_name": "Asha Roy", "password": "S3cure-pass" }

POST /auth/login
{ "email": "asha@example.com", "password": "S3cure-pass" }
-> 200 { "access_token": "<jwt>", "token_type": "bearer", "expires_in": 3600 }

POST /bookings          (Authorization: Bearer <jwt>)
{ "centre_id": "<uuid>", "test_id": "<uuid>", "appointment_at": "2026-10-15T09:30:00Z" }
-> 201 { "id": "<uuid>", "status": "PENDING", "amount": "850.00" }

POST /payments/         (Authorization: Bearer <jwt>)
{ "booking_id": "<uuid>", "simulate": "SUCCESS" }
-> 201 { "payment_id": "<uuid>", "status": "SUCCESS", "booking_status": "CONFIRMED" }

POST /payments/webhook/  (X-Signature: <hmac-sha256-hex of raw body>)
{ "event_id": "evt_1001", "provider_reference": "pay_abc123",
  "booking_id": "<uuid>", "status": "SUCCESS", "amount": "850.00",
  "occurred_at": "2026-10-01T10:00:00Z" }
-> 200 { "status": "processed" }     (repeat -> 200 { "status": "duplicate" })
```

---

## 9. Edge Cases and Error Handling

| Scenario | Expected behaviour | HTTP |
|---|---|---|
| Invalid / missing fields, bad email, short password | Pydantic validation error with field details | 422 |
| Duplicate signup email | Reject; reveal no more than needed | 409 |
| Wrong password / unknown user | Generic invalid-credentials message | 401 |
| Missing, malformed or expired JWT | Reject | 401 |
| Non-admin calls admin endpoint | Reject | 403 |
| Booking ID malformed (not a UUID) | Validation error | 422 |
| Booking ID does not exist | Not found | 404 |
| Accessing / paying / cancelling another user's booking | 404 (avoid leaking existence) or 403; be consistent and document | 404 / 403 |
| Centre does not offer requested test | Business rule error | 422 |
| Appointment in the past | Validation error | 422 |
| Pay for a booking not in PENDING | State conflict | 409 |
| Payment result FAILED | Payment row FAILED, booking FAILED, clear response body | 201 |
| Duplicate webhook (same `event_id`), sequential or concurrent | No new rows, no state change, return duplicate | 200 |
| Webhook with bad signature | Reject, log, no DB writes | 401 |
| Webhook for unknown booking | Record event, no state change | 404 |
| Late SUCCESS webhook for a CANCELLED booking | Ignore transition, log warning, mark event IGNORED | 200 |
| FAILED webhook after SUCCESS | Never downgrade; ignore and log | 200 |
| Webhook amount differs from booking amount | Reject and log | 422 |
| Unhandled server error | Log with request id; generic message, no stack trace | 500 |

---

## 10. Non-Functional Requirements

- **Security:** bcrypt password hashing, JWT secret from env, HMAC verification with constant-time comparison, no secrets committed (`.env.example` only), ORM parameterised queries, explicit CORS config.
- **Transactions:** booking status and payment writes are atomic. Use `SELECT ... FOR UPDATE` for state changes.
- **Logging:** structured JSON logs with request id, user id, booking id, event id. Never log passwords, tokens or the webhook secret.
- **Performance:** indexes from section 6; pagination on all list endpoints (default 20, max 100).
- **Configuration:** `DATABASE_URL`, `JWT_SECRET`, `JWT_EXPIRE_MINUTES`, `WEBHOOK_SECRET`, `PAYMENT_SUCCESS_RATE`, `ADMIN_EMAIL` / `ADMIN_PASSWORD` via env.
- **Code quality:** type hints, small functions, consistent naming, linting (ruff) and formatting, no dead code.

---

## 11. Bonus Items (Prioritised)

| Priority | Item | Note |
|---|---|---|
| 1 | Docker + docker-compose (api + postgres) | Cheap, high reviewer value; must work with one command |
| 2 | Swagger / OpenAPI | Free with FastAPI; add summaries, examples, error responses |
| 3 | Pagination + filters | limit/offset with total count |
| 4 | Structured logging | JSON logs with request id middleware |
| 5 | Tests beyond minimum | Concurrency test for duplicate webhooks |
| 6 | Rate limiting | e.g. slowapi on `/auth/login` |
| 7 | Webhook retry handling | Provider-side retry simulation; our side already idempotent |
| 8 | Redis caching / Celery | Only if time allows; cache centre listing, async webhook processing |

---

## 12. Testing Requirements

Use a real PostgreSQL test database (docker-compose service or testcontainers), not SQLite, because row locks and partial indexes must be exercised. Each test runs in an isolated transaction or clean schema.

| Area | Minimum tests |
|---|---|
| Auth | signup success, duplicate email, weak password, login success, wrong password, protected route without token, expired token |
| Centres / tests | admin create + attach price, non-admin forbidden, list with pagination and filter |
| Bookings | create with amount snapshot, test not offered at centre, past date, unknown booking, other user's booking blocked, cancel rules |
| Payments | SUCCESS confirms booking, FAILED marks booking FAILED, pay non-PENDING booking 409, other user's booking blocked, idempotency key reuse |
| Webhook | valid event processed, bad signature 401, **same event twice yields one payment and one state change**, concurrent duplicate deliveries, out-of-order FAILED after SUCCESS ignored, late SUCCESS on CANCELLED ignored, unknown booking, amount mismatch |
| State machine | unit tests for every allowed and disallowed transition |

---

## 13. Deliverables and Definition of Done

### Repository must contain
- Source code following section 4, with a clean, incremental Git history (small commits, meaningful messages).
- `README.md`, `requirements.txt` (or `pyproject.toml`), `Dockerfile`, `docker-compose.yml`, `.env.example`, Alembic migrations, tests.

### README must explain
- How to run locally (with and without Docker), run migrations, seed an admin, run tests.
- API endpoints with example requests and responses (curl or Swagger link).
- Database schema design (ER diagram or table list) and reasoning.
- How webhook idempotency and the booking state machine work.
- Assumptions made (section 14).
- What would be improved with more time (real provider integration, refunds, slot capacity, async processing with Celery, observability, CI pipeline).

### Definition of done
- [ ] Every Must requirement implemented and demonstrable through Swagger.
- [ ] All tests pass locally and in a clean Docker environment; `docker compose up` brings up a working system.
- [ ] Duplicate webhook scenario proven by an automated test.
- [ ] No secrets in the repository; linter passes.
- [ ] The developer can explain every design decision (the next interview stage may include a live architecture walkthrough and a small live code change).

---

## 14. Assumptions (confirm or document in the README)

- Money is in INR with two decimals; single currency.
- No slot capacity or double-booking rules per centre.
- A FAILED booking is terminal; the user creates a new booking to retry payment. (Alternative: allow FAILED to PENDING retry. Choose one and document it.)
- Cancelling a CONFIRMED booking does not trigger a refund flow (out of scope).
- Catalogue endpoints are readable by any authenticated user; writes are admin only.
- The webhook provider signs payloads with a shared HMAC secret and supplies a unique `event_id` per event.
- Time values are ISO 8601 and stored in UTC.


*End of document.*
