from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://eve:eve@localhost:5432/eve_db"
    DATABASE_URL_TEST: str = "postgresql://eve:eve@localhost:5432/eve_test_db"
    JWT_SECRET: str = "change-me-to-a-random-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    WEBHOOK_SECRET: str = "change-me-to-another-random-secret"
    PAYMENT_SUCCESS_RATE: float = 0.80
    ADMIN_EMAIL: str = "admin@eve.com"
    ADMIN_PASSWORD: str = "admin1234"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
