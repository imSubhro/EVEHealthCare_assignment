import logging
import time

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes import auth, bookings, centres, payments
from app.core.logging import generate_request_id, request_id_var, setup_logging

logger = logging.getLogger("eve.access")

app = FastAPI(
    title="EVE Healthcare - Diagnostic Test Booking API",
    description="Backend service for browsing diagnostic centres, booking tests, and simulated payments.",
    version="1.0.0",
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or generate_request_id()
    token = request_id_var.set(request_id)
    request.state.request_id = request_id
    started = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    logger.info(
        "request completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    if errors:
        first = errors[0]
        field = " -> ".join(str(loc) for loc in first.get("loc", []))
        msg = first.get("msg", "Validation error")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": f"{field}: {msg}", "code": "VALIDATION_ERROR"},
        )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation error", "code": "VALIDATION_ERROR"},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "")
    token = request_id_var.set(request_id)
    try:
        logger.exception(
            "unhandled server error",
            extra={"path": request.url.path, "method": request.method},
        )
    finally:
        request_id_var.reset(token)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error", "code": "INTERNAL_ERROR"},
        headers={"X-Request-ID": request_id} if request_id else None,
    )


app.include_router(auth.router)
app.include_router(centres.router)
app.include_router(bookings.router)
app.include_router(payments.router)


@app.on_event("startup")
def on_startup():
    setup_logging()


@app.get("/health")
def health_check():
    return {"status": "ok"}
