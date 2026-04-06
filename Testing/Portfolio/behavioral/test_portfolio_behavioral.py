"""
test_portfolio_behavioral.py,  BEHAVIORAL TESTS
Behavioral / end-to-end API tests for the portfolio management system.

Notes
-----
Tests run against an in-memory SQLite database via FastAPI TestClient.
Covers the full portfolio lifecycle, authentication enforcement,
input validation, and cross-user isolation.
"""

from __future__ import annotations

import os
import sys
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ---------------------------------------------------------------------------
# Import path setup
# ---------------------------------------------------------------------------

def _configure_paths() -> None:
    here = os.path.abspath(os.path.dirname(__file__))
    repo_root = os.path.abspath(os.path.join(here, "..", "..", ".."))
    backend_root = os.path.join(repo_root, "backend")
    for candidate in ("/app", backend_root, repo_root):
        if os.path.isdir(candidate) and candidate not in sys.path:
            sys.path.insert(0, candidate)

_configure_paths()

from app.db.base import Base
from app.db.main import get_db
from app.models.models import User, Portfolio, PriceAlert
from app.api import auth as auth_module
from app.api import portfolio as portfolio_module

# ---------------------------------------------------------------------------
# Test app + fixtures
# ---------------------------------------------------------------------------

_TEST_DB_URL = "sqlite:///:memory:"
_engine = create_engine(_TEST_DB_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
_Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

Base.metadata.create_all(
    bind=_engine,
    tables=[User.__table__, Portfolio.__table__, PriceAlert.__table__],
)

with _engine.begin() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            ticker TEXT NOT NULL,
            action TEXT NOT NULL,
            quantity REAL NOT NULL,
            price REAL NOT NULL,
            realized_gain REAL,
            executed_at TEXT DEFAULT (datetime('now'))
        )
    """))


def _override_get_db():
    db = _Session()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def client():
    app = FastAPI()
    app.include_router(auth_module.router, prefix="/api")
    app.include_router(portfolio_module.router, prefix="/api")
    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


def _register_and_login(client, email: str, username: str, password: str = "Pass99!x") -> str:
    client.post("/api/auth/register", json={
        "email": email, "username": username,
        "password": password, "confirm_password": password,
    })
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(client):
    token = _register_and_login(client, "port_beh@example.com", "port_beh_user")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def other_headers(client):
    token = _register_and_login(client, "port_other@example.com", "port_other_user")
    return {"Authorization": f"Bearer {token}"}


PORTFOLIO_URL = "/api/portfolio"


# ===========================================================================
# BEHAVIORAL: Authentication guard
# ===========================================================================

class TestPortfolioAuthGuard:
    def test_list_requires_auth(self, client):
        """GET /portfolio without token returns 401."""
        assert client.get(PORTFOLIO_URL).status_code == 401

    def test_add_requires_auth(self, client):
        """POST /portfolio without token returns 401."""
        res = client.post(PORTFOLIO_URL, json={"ticker": "AAPL", "quantity": 1.0, "avg_price": 150.0})
        assert res.status_code == 401

    def test_get_item_requires_auth(self, client):
        """GET /portfolio/{ticker} without token returns 401."""
        assert client.get(f"{PORTFOLIO_URL}/AAPL").status_code == 401

    def test_update_requires_auth(self, client):
        """PUT /portfolio/{ticker} without token returns 401."""
        assert client.put(f"{PORTFOLIO_URL}/AAPL", json={"quantity": 5.0}).status_code == 401

    def test_delete_requires_auth(self, client):
        """DELETE /portfolio/{ticker} without token returns 401."""
        assert client.delete(f"{PORTFOLIO_URL}/AAPL").status_code == 401


# ===========================================================================
# BEHAVIORAL: Full position lifecycle
# ===========================================================================

class TestPortfolioLifecycle:
    def test_empty_portfolio_on_registration(self, client, auth_headers):
        """A new user has an empty portfolio."""
        res = client.get(PORTFOLIO_URL, headers=auth_headers)
        assert res.status_code == 200
        assert res.json() == []

    def test_add_first_position(self, client, auth_headers):
        """Adding a new position returns 201 with correct fields."""
        res = client.post(PORTFOLIO_URL, headers=auth_headers, json={
            "ticker": "AAPL", "quantity": 10.0, "avg_price": 150.00,
        })
        assert res.status_code == 201
        data = res.json()
        assert data["ticker"] == "AAPL"
        assert float(data["quantity"]) == 10.0
        assert float(data["avg_price"]) == pytest.approx(150.0)

    def test_position_appears_in_list(self, client, auth_headers):
        """The added position is returned by GET /portfolio."""
        tickers = [p["ticker"] for p in client.get(PORTFOLIO_URL, headers=auth_headers).json()]
        assert "AAPL" in tickers

    def test_get_individual_position(self, client, auth_headers):
        """GET /portfolio/AAPL returns the correct position."""
        res = client.get(f"{PORTFOLIO_URL}/AAPL", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["ticker"] == "AAPL"

    def test_adding_more_shares_averages_price(self, client, auth_headers):
        """
        Adding shares of an already-held ticker updates quantity and computes
        weighted average price: (10 * 150 + 10 * 200) / 20 = 175.
        """
        res = client.post(PORTFOLIO_URL, headers=auth_headers, json={
            "ticker": "AAPL", "quantity": 10.0, "avg_price": 200.00,
        })
        assert res.status_code == 201
        data = res.json()
        assert float(data["quantity"]) == pytest.approx(20.0)
        assert float(data["avg_price"]) == pytest.approx(175.0, rel=1e-3)

    def test_add_second_ticker(self, client, auth_headers):
        """Adding a different ticker creates a separate, independent position."""
        res = client.post(PORTFOLIO_URL, headers=auth_headers, json={
            "ticker": "TSLA", "quantity": 5.0, "avg_price": 250.00,
        })
        assert res.status_code == 201
        assert res.json()["ticker"] == "TSLA"

    def test_update_quantity(self, client, auth_headers):
        """PUT /portfolio/TSLA can update quantity independently."""
        res = client.put(f"{PORTFOLIO_URL}/TSLA", headers=auth_headers,
                         json={"quantity": 8.0})
        assert res.status_code == 200
        assert float(res.json()["quantity"]) == 8.0

    def test_update_avg_price(self, client, auth_headers):
        """PUT /portfolio/TSLA can update avg_price independently."""
        res = client.put(f"{PORTFOLIO_URL}/TSLA", headers=auth_headers,
                         json={"avg_price": 300.00})
        assert res.status_code == 200
        assert float(res.json()["avg_price"]) == pytest.approx(300.0)

    # def test_delete_position(self, client, auth_headers):
    #     """DELETE /portfolio/TSLA removes the position."""
    #     res = client.delete(f"{PORTFOLIO_URL}/TSLA", headers=auth_headers)
    #     assert res.status_code == 200

    # def test_deleted_position_returns_404(self, client, auth_headers):
    #     """After deletion, GET /portfolio/TSLA returns 404."""
    #     res = client.get(f"{PORTFOLIO_URL}/TSLA", headers=auth_headers)
    #     assert res.status_code == 404


# ===========================================================================
# BEHAVIORAL: Not-found handling
# ===========================================================================

class TestPortfolioNotFound:
    def test_get_unknown_ticker_404(self, client, auth_headers):
        """GET /portfolio/FAKE returns 404."""
        assert client.get(f"{PORTFOLIO_URL}/FAKE", headers=auth_headers).status_code == 404

    def test_update_unknown_ticker_404(self, client, auth_headers):
        """PUT /portfolio/FAKE returns 404."""
        assert client.put(f"{PORTFOLIO_URL}/FAKE", headers=auth_headers,
                          json={"quantity": 1.0}).status_code == 404

    def test_delete_unknown_ticker_404(self, client, auth_headers):
        """DELETE /portfolio/FAKE returns 404."""
        assert client.delete(f"{PORTFOLIO_URL}/FAKE", headers=auth_headers).status_code == 404


# ===========================================================================
# BEHAVIORAL: Cross-user isolation
# ===========================================================================

class TestPortfolioIsolation:
    def test_users_only_see_own_positions(self, client, auth_headers, other_headers):
        """Each user's portfolio is completely independent."""
        client.post(PORTFOLIO_URL, headers=auth_headers, json={
            "ticker": "ISOLATED_A", "quantity": 1.0, "avg_price": 10.0,
        })
        client.post(PORTFOLIO_URL, headers=other_headers, json={
            "ticker": "ISOLATED_B", "quantity": 2.0, "avg_price": 20.0,
        })

        user1 = {p["ticker"] for p in client.get(PORTFOLIO_URL, headers=auth_headers).json()}
        user2 = {p["ticker"] for p in client.get(PORTFOLIO_URL, headers=other_headers).json()}

        assert "ISOLATED_A" in user1
        assert "ISOLATED_B" not in user1
        assert "ISOLATED_B" in user2
        assert "ISOLATED_A" not in user2

    def test_user_cannot_access_other_users_position(self, client, auth_headers, other_headers):
        """User B gets 404 when accessing User A's specific ticker."""
        client.post(PORTFOLIO_URL, headers=auth_headers, json={
            "ticker": "PRIVATE_A", "quantity": 5.0, "avg_price": 100.0,
        })
        res = client.get(f"{PORTFOLIO_URL}/PRIVATE_A", headers=other_headers)
        assert res.status_code == 404
