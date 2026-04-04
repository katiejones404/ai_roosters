"""
conftest.py
Shared pytest fixtures for unit and behavioral tests.

Notes
-----
Uses an in-memory SQLite database to avoid requiring a live PostgreSQL connection.
Only the tables needed for auth, portfolio, and alert tests are created.
The get_db dependency is overridden so all API calls use the test session.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.main import get_db
from app.models.models import User, Portfolio, PriceAlert
from app.api import auth as auth_module
from app.api import portfolio as portfolio_module
from app.api import alerts as alerts_module

TEST_DB_URL = "sqlite:///:memory:"

engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create only the tables needed for tests (avoids PostgreSQL-specific types in other models)
Base.metadata.create_all(bind=engine, tables=[
    User.__table__,
    Portfolio.__table__,
    PriceAlert.__table__,
])


def override_get_db():
    """
    Yield a SQLite test session, replacing the production PostgreSQL session.
    """
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def build_test_app() -> FastAPI:
    """
    Build a minimal FastAPI app with auth, portfolio, and alert routers.

    Notes
    -----
    No startup events are registered, so no pipelines or DB migrations run.
    """
    app = FastAPI()
    app.include_router(auth_module.router, prefix="/api/auth")
    app.include_router(portfolio_module.router, prefix="/api")
    app.include_router(alerts_module.router, prefix="/api/alerts")
    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.fixture(scope="module")
def client():
    """Return a TestClient for the minimal test app."""
    return TestClient(build_test_app())


@pytest.fixture(scope="module")
def registered_user():
    """Return credentials for a test user."""
    return {
        "email": "testuser@example.com",
        "username": "testuser",
        "password": "TestPass123!",
        "confirm_password": "TestPass123!",
    }


@pytest.fixture(scope="module")
def auth_headers(client, registered_user):
    """
    Register and log in a test user, returning Authorization headers.

    Notes
    -----
    Uses module scope so the user is only created once per test module.
    If the user already exists from a prior test, login still succeeds.
    """
    client.post("/api/auth/register", json=registered_user)
    response = client.post("/api/auth/login", json={
        "email": registered_user["email"],
        "password": registered_user["password"],
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
