import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.db.session import Base, get_db
from app.main import app
from app.core.config import get_settings
from app.core.security import create_access_token

settings = get_settings()
TEST_DB_URL = settings.DATABASE_URL_TEST


def ensure_database(url: str) -> None:
    admin_url = make_url(url).set(database="postgres")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": make_url(url).database},
            ).scalar()
            if not exists:
                conn.execute(
                    text(f'CREATE DATABASE "{make_url(url).database}"')
                )
    finally:
        admin_engine.dispose()


ensure_database(TEST_DB_URL)
engine = create_engine(TEST_DB_URL, pool_pre_ping=True)
TestSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="function", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def admin_token():
    return create_access_token("admin-test-id", is_admin=True)


@pytest.fixture
def user_token():
    return create_access_token("user-test-id", is_admin=False)


def make_auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
