import hashlib
import hmac
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import get_settings

settings = get_settings()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: str, is_admin: bool = False) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "is_admin": is_admin,
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


def compute_hmac_signature(body: bytes) -> str:
    return hmac.new(settings.WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


def verify_hmac_signature(body: bytes, signature: str) -> bool:
    expected = compute_hmac_signature(body)
    return hmac.compare_digest(expected, signature)
