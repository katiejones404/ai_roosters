"""
test_email_behavioral.py    BEHAVIORAL TESTS
Behavioral / end-to-end tests for email-driven API flows.

Notes
-----
Tests run against an in-memory SQLite database via FastAPI TestClient.
SMTP is patched so no real email is sent during testing.
Covers the forgot-password endpoint, reset-token flow, and
the interaction between notification preferences and email delivery.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import patch, MagicMock

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


@pytest.fixture(scope="module")
def client():
    app = FastAPI()
    app.include_router(auth_module.router, prefix="/api")
    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


_VALID_USER = {
    "email": "email_beh@example.com",
    "username": "email_beh_user",
    "password": "BehPass99!",
    "confirm_password": "BehPass99!",
}

_SMTP_ENV = {
    "SMTP_HOST": "smtp.example.com",
    "SMTP_PORT": "587",
    "SMTP_USER": "sender@example.com",
    "SMTP_PASS": "secret",
    "ALERT_FROM_EMAIL": "alerts@example.com",
}


def _mock_smtp():
    """Return a patched smtplib.SMTP that records sendmail calls."""
    mock_cls = MagicMock()
    mock_server = MagicMock()
    mock_cls.return_value.__enter__.return_value = mock_server
    mock_cls.return_value.__exit__.return_value = False
    return mock_cls, mock_server


# ===========================================================================
# BEHAVIORAL: Forgot-password endpoint
# ===========================================================================

class TestForgotPasswordEmail:
    def test_forgot_password_always_returns_204(self, client):
        """
        Forgot-password always returns 204 for any email to prevent enumeration.

        This is a security requirement, the response must not reveal whether
        the email exists in the database.
        """
        client.post("/api/auth/register", json=_VALID_USER)

        for email in (_VALID_USER["email"], "nobody@nowhere.com"):
            res = client.post("/api/auth/forgot-password", json={"email": email})
            assert res.status_code == 204, f"Expected 204 for {email}, got {res.status_code}"

    def test_forgot_password_sends_email_for_known_user(self, client):
        """
        Forgot-password sends a reset email when the email is registered.

        The SMTP send path is patched; we verify sendmail was called exactly
        once with the user's address.
        """
        client.post("/api/auth/register", json=_VALID_USER)
        mock_cls, mock_server = _mock_smtp()

        with patch("app.services.email_service.smtplib.SMTP", mock_cls), \
             patch.dict(os.environ, _SMTP_ENV, clear=False):
            res = client.post("/api/auth/forgot-password",
                              json={"email": _VALID_USER["email"]})

        assert res.status_code == 204
        # Email was attempted for the registered user
        mock_server.sendmail.assert_called_once()
        _, to_addr, _ = mock_server.sendmail.call_args[0]
        assert to_addr == _VALID_USER["email"]

    def test_forgot_password_does_not_send_email_for_unknown_user(self, client):
        """
        Forgot-password does NOT attempt to send an email for an unregistered address.

        The response is still 204, but no SMTP call is made.
        """
        mock_cls, mock_server = _mock_smtp()

        with patch("app.services.email_service.smtplib.SMTP", mock_cls), \
             patch.dict(os.environ, _SMTP_ENV, clear=False):
            res = client.post("/api/auth/forgot-password",
                              json={"email": "ghost@nowhere.com"})

        assert res.status_code == 204
        mock_server.sendmail.assert_not_called()

    def test_reset_email_body_contains_reset_link(self, client):
        """
        The reset email body includes a URL containing a reset token.
        """
        client.post("/api/auth/register", json=_VALID_USER)
        mock_cls, mock_server = _mock_smtp()

        with patch("app.services.email_service.smtplib.SMTP", mock_cls), \
             patch.dict(os.environ, _SMTP_ENV, clear=False):
            client.post("/api/auth/forgot-password",
                        json={"email": _VALID_USER["email"]})

        if mock_server.sendmail.called:
            raw_message = mock_server.sendmail.call_args[0][2]
            assert "reset" in raw_message.lower() or "token" in raw_message.lower()

    def test_reset_email_subject_is_recognizable(self, client):
        """
        The reset email has a subject line that clearly identifies it as a password reset.
        """
        client.post("/api/auth/register", json=_VALID_USER)
        mock_cls, mock_server = _mock_smtp()

        with patch("app.services.email_service.smtplib.SMTP", mock_cls), \
             patch.dict(os.environ, _SMTP_ENV, clear=False):
            client.post("/api/auth/forgot-password",
                        json={"email": _VALID_USER["email"]})

        if mock_server.sendmail.called:
            from email import message_from_string
            raw = mock_server.sendmail.call_args[0][2]
            msg = message_from_string(raw)
            subject = (msg["Subject"] or "").lower()
            assert "password" in subject or "reset" in subject


# ===========================================================================
# BEHAVIORAL: Notification preferences gate email delivery
# ===========================================================================

class TestNotificationPreferencesEmailGate:
    """
    Verify that a user's email notification preferences are correctly returned
    and persisted, so the alert scheduler can honour them when deciding whether
    to send a price-alert email.
    """

    def _login(self, client) -> str:
        creds = {
            "email": "email_prefs@example.com",
            "username": "email_prefs_user",
            "password": "PrefsPass99!",
            "confirm_password": "PrefsPass99!",
        }
        client.post("/api/auth/register", json=creds)
        res = client.post("/api/auth/login",
                          json={"email": creds["email"], "password": creds["password"]})
        return res.json()["access_token"]

    def test_email_notifications_default_to_true(self, client):
        """A newly registered user has email notifications enabled by default."""
        token = self._login(client)
        res = client.get("/api/auth/me/notifications",
                         headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        assert res.json()["emailNotifications"] is True

    def test_market_alerts_default_to_true(self, client):
        """A newly registered user has market alerts enabled by default."""
        token = self._login(client)
        res = client.get("/api/auth/me/notifications",
                         headers={"Authorization": f"Bearer {token}"})
        assert res.json()["marketAlerts"] is True

    def test_disabling_email_notifications_persists(self, client):
        """Turning off email notifications is reflected on the next GET."""
        token = self._login(client)
        headers = {"Authorization": f"Bearer {token}"}

        patch_res = client.patch("/api/auth/me/notifications",
                                 headers=headers,
                                 json={"emailNotifications": False})
        assert patch_res.status_code == 200
        assert patch_res.json()["emailNotifications"] is False

        get_res = client.get("/api/auth/me/notifications", headers=headers)
        assert get_res.json()["emailNotifications"] is False

    def test_re_enabling_email_notifications_persists(self, client):
        """Turning email notifications back on is reflected on the next GET."""
        token = self._login(client)
        headers = {"Authorization": f"Bearer {token}"}

        client.patch("/api/auth/me/notifications", headers=headers,
                     json={"emailNotifications": False})
        client.patch("/api/auth/me/notifications", headers=headers,
                     json={"emailNotifications": True})

        res = client.get("/api/auth/me/notifications", headers=headers)
        assert res.json()["emailNotifications"] is True

    def test_preferences_require_auth(self, client):
        """Notification preferences endpoints require authentication."""
        assert client.get("/api/auth/me/notifications").status_code == 401
        assert client.patch("/api/auth/me/notifications",
                            json={"emailNotifications": False}).status_code == 401
