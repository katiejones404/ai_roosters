"""
test_alerts_behavioral.py,  BEHAVIORAL TESTS
Behavioral / end-to-end API tests for the price alert system.

Notes
-----
Tests run against an in-memory SQLite database via FastAPI TestClient.
All user-facing workflows are covered: create, list, delete, validation,
cross-user isolation, and authentication enforcement.
"""

from __future__ import annotations

import os
import sys
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
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
from app.api import alerts as alerts_module

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


def _override_get_db():
    db = _Session()
    try:
        yield db
    finally:
        db.close()


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth_module.router, prefix="/api")
    app.include_router(alerts_module.router, prefix="/api/alerts")
    app.dependency_overrides[get_db] = _override_get_db
    return app


@pytest.fixture(scope="module")
def client():
    """TestClient wired to in-memory SQLite."""
    return TestClient(_build_app())


def _register_and_login(client, email: str, username: str, password: str = "Pass99!x") -> str:
    client.post("/api/auth/register", json={
        "email": email, "username": username,
        "password": password, "confirm_password": password,
    })
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}"
    return res.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(client):
    token = _register_and_login(client, "alerts_beh@example.com", "alerts_beh_user")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def other_headers(client):
    """Second user, used for isolation checks."""
    token = _register_and_login(client, "alerts_other@example.com", "alerts_other_user")
    return {"Authorization": f"Bearer {token}"}


ALERTS_URL = "/api/alerts"

VALID_ALERT = {
    "ticker": "AAPL",
    "target_price": 200.00,
    "direction": "above",
    "email_notify": True,
}


# ===========================================================================
# BEHAVIORAL: Authentication guard
# ===========================================================================

class TestAlertAuthGuard:
    def test_list_requires_auth(self, client):
        """GET /alerts without token returns 401."""
        assert client.get(ALERTS_URL).status_code == 401

    def test_create_requires_auth(self, client):
        """POST /alerts without token returns 401."""
        assert client.post(ALERTS_URL, json=VALID_ALERT).status_code == 401

    def test_delete_requires_auth(self, client):
        """DELETE /alerts/{id} without token returns 401."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        assert client.delete(f"{ALERTS_URL}/{fake_id}").status_code == 401


# ===========================================================================
# BEHAVIORAL: Full alert lifecycle
# ===========================================================================

class TestAlertLifecycle:
    def test_new_user_has_empty_alert_list(self, client, auth_headers):
        """A freshly registered user has no alerts."""
        res = client.get(ALERTS_URL, headers=auth_headers)
        assert res.status_code == 200
        assert res.json() == []

    def test_create_alert_above_returns_201(self, client, auth_headers):
        """Creating a 'rises above' alert succeeds with all required fields."""
        res = client.post(ALERTS_URL, headers=auth_headers, json=VALID_ALERT)
        assert res.status_code == 201
        data = res.json()
        assert data["ticker"] == "AAPL"
        assert data["direction"] == "above"
        assert float(data["target_price"]) == 200.00
        assert data["is_active"] is True
        assert "id" in data

    def test_created_alert_appears_in_list(self, client, auth_headers):
        """The created alert shows up in the user's alert list."""
        res = client.get(ALERTS_URL, headers=auth_headers)
        assert res.status_code == 200
        tickers = [a["ticker"] for a in res.json()]
        assert "AAPL" in tickers

    def test_create_alert_below(self, client, auth_headers):
        """Creating a 'falls below' alert works and returns the correct direction."""
        res = client.post(ALERTS_URL, headers=auth_headers, json={
            "ticker": "TSLA",
            "target_price": 150.00,
            "direction": "below",
            "email_notify": False,
        })
        assert res.status_code == 201
        assert res.json()["direction"] == "below"

    def test_list_shows_multiple_alerts(self, client, auth_headers):
        """Both alerts created above are returned."""
        res = client.get(ALERTS_URL, headers=auth_headers)
        tickers = [a["ticker"] for a in res.json()]
        assert "AAPL" in tickers
        assert "TSLA" in tickers

    def test_delete_alert_returns_204(self, client, auth_headers):
        """Deleting an existing alert returns 204."""
        alert_id = client.post(ALERTS_URL, headers=auth_headers, json={
            "ticker": "NVDA", "target_price": 500.0,
            "direction": "above", "email_notify": False,
        }).json()["id"]

        res = client.delete(f"{ALERTS_URL}/{alert_id}", headers=auth_headers)
        assert res.status_code == 204

    def test_deleted_alert_absent_from_list(self, client, auth_headers):
        """A deleted alert is not returned by the list endpoint."""
        alert_id = client.post(ALERTS_URL, headers=auth_headers, json={
            "ticker": "AMD", "target_price": 100.0,
            "direction": "below", "email_notify": True,
        }).json()["id"]

        client.delete(f"{ALERTS_URL}/{alert_id}", headers=auth_headers)

        ids = [a["id"] for a in client.get(ALERTS_URL, headers=auth_headers).json()]
        assert alert_id not in ids

    def test_delete_nonexistent_alert_returns_404(self, client, auth_headers):
        """Deleting an alert that doesn't exist returns 404."""
        res = client.delete(f"{ALERTS_URL}/00000000-0000-0000-0000-000000000000",
                            headers=auth_headers)
        assert res.status_code == 404


# ===========================================================================
# BEHAVIORAL: Input validation
# ===========================================================================

class TestAlertValidation:
    def test_invalid_direction_rejected(self, client, auth_headers):
        """An unrecognized direction value is rejected with 400."""
        res = client.post(ALERTS_URL, headers=auth_headers, json={
            "ticker": "AAPL", "target_price": 200.0,
            "direction": "sideways", "email_notify": True,
        })
        assert res.status_code == 400

    def test_negative_target_price_rejected(self, client, auth_headers):
        """A negative target price is rejected with 400."""
        res = client.post(ALERTS_URL, headers=auth_headers, json={
            "ticker": "AAPL", "target_price": -50.0,
            "direction": "above", "email_notify": True,
        })
        assert res.status_code == 400

    def test_zero_target_price_rejected(self, client, auth_headers):
        """A zero target price is rejected with 400."""
        res = client.post(ALERTS_URL, headers=auth_headers, json={
            "ticker": "AAPL", "target_price": 0.0,
            "direction": "above", "email_notify": True,
        })
        assert res.status_code == 400


# ==========================================================
# BEHAVIORAL: Cross-user isolation
# ===========================================================

class TestAlertIsolation:
    def test_users_cannot_see_each_others_alerts(self, client, auth_headers, other_headers):
        """Each user only sees their own alerts, not another user's."""
        client.post(ALERTS_URL, headers=auth_headers, json={
            "ticker": "ISOLATE1", "target_price": 100.0,
            "direction": "above", "email_notify": False,
        })
        client.post(ALERTS_URL, headers=other_headers, json={
            "ticker": "ISOLATE2", "target_price": 200.0,
            "direction": "below", "email_notify": False,
        })

        user1_alerts = client.get(ALERTS_URL, headers=auth_headers).json()
        user2_alerts = client.get(ALERTS_URL, headers=other_headers).json()

        user1_tickers = {a["ticker"] for a in user1_alerts}
        user2_tickers = {a["ticker"] for a in user2_alerts}

        assert "ISOLATE1" in user1_tickers
        assert "ISOLATE2" not in user1_tickers
        assert "ISOLATE2" in user2_tickers
        assert "ISOLATE1" not in user2_tickers

    def test_user_cannot_delete_other_users_alert(self, client, auth_headers, other_headers):
        """User B cannot delete an alert belonging to User A."""
        alert_id = client.post(ALERTS_URL, headers=auth_headers, json={
            "ticker": "PROTECTED", "target_price": 50.0,
            "direction": "above", "email_notify": False,
        }).json()["id"]

        res = client.delete(f"{ALERTS_URL}/{alert_id}", headers=other_headers)
        assert res.status_code == 404
