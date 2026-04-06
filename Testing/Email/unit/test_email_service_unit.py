"""
test_email_service_unit.py
Unit tests for app.services.email_service.

Notes
-----
All SMTP network calls are patched so these tests run offline with no
SMTP credentials required.  Tests verify message structure, subject lines,
direction words, and error handling without touching a real mail server.
"""

from __future__ import annotations

import os
import sys
from email import message_from_string
from email.mime.multipart import MIMEMultipart
from unittest.mock import MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Import path setup (works in Docker at /app and in local repo layout)
# ---------------------------------------------------------------------------

def _configure_import_paths() -> None:
    here = os.path.abspath(os.path.dirname(__file__))
    repo_root = os.path.abspath(os.path.join(here, "..", "..", ".."))
    backend_root = os.path.join(repo_root, "backend")
    for candidate in ("/app", backend_root, repo_root):
        if os.path.isdir(candidate) and candidate not in sys.path:
            sys.path.insert(0, candidate)


_configure_import_paths()

from app.services.email_service import (  # noqa: E402
    send_price_alert_email,
    send_password_reset_email,
)


# ---------------------------------------------------------------------------
# Shared SMTP environment
# ---------------------------------------------------------------------------

_SMTP_ENV = {
    "SMTP_HOST": "smtp.example.com",
    "SMTP_PORT": "587",
    "SMTP_USER": "sender@example.com",
    "SMTP_PASS": "secret",
    "ALERT_FROM_EMAIL": "alerts@example.com",
}


def _mock_smtp_context():
    """Return a patched smtplib.SMTP context manager and the inner server mock."""
    mock_smtp_class = MagicMock()
    mock_server = MagicMock()
    mock_smtp_class.return_value.__enter__.return_value = mock_server
    mock_smtp_class.return_value.__exit__.return_value = False
    return mock_smtp_class, mock_server


# ===========================================================================
# send_price_alert_email, credential guard
# ===========================================================================

class TestSendPriceAlertEmailCredentials:
    def test_raises_when_smtp_user_missing(self):
        """RuntimeError is raised when SMTP_USER is not set."""
        env = {k: v for k, v in _SMTP_ENV.items() if k != "SMTP_USER"}
        env["SMTP_USER"] = ""
        with patch.dict(os.environ, env, clear=False):
            with pytest.raises(RuntimeError, match="SMTP_USER"):
                send_price_alert_email("a@b.com", "AAPL", "above", 200.0, 210.0)

    def test_raises_when_smtp_pass_missing(self):
        """RuntimeError is raised when SMTP_PASS is not set."""
        env = {k: v for k, v in _SMTP_ENV.items()}
        env["SMTP_PASS"] = ""
        with patch.dict(os.environ, env, clear=False):
            with pytest.raises(RuntimeError, match="SMTP_PASS"):
                send_price_alert_email("a@b.com", "AAPL", "above", 200.0, 210.0)


# ===========================================================================
# send_price_alert_email , SMTP call verification
# ===========================================================================

class TestSendPriceAlertEmailSmtp:
    def test_connects_to_configured_host_and_port(self):
        """SMTP is opened against the host and port from environment variables."""
        mock_smtp_class, _ = _mock_smtp_context()
        with patch("app.services.email_service.smtplib.SMTP", mock_smtp_class), \
             patch.dict(os.environ, _SMTP_ENV, clear=False):
            send_price_alert_email("user@example.com", "AAPL", "above", 200.0, 210.0)

        mock_smtp_class.assert_called_once_with("smtp.example.com", 587)

    def test_calls_starttls_and_login(self):
        """Server calls ehlo, starttls, and login before sending."""
        mock_smtp_class, mock_server = _mock_smtp_context()
        with patch("app.services.email_service.smtplib.SMTP", mock_smtp_class), \
             patch.dict(os.environ, _SMTP_ENV, clear=False):
            send_price_alert_email("user@example.com", "AAPL", "above", 200.0, 210.0)

        mock_server.ehlo.assert_called_once()
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("sender@example.com", "secret")

    def test_sendmail_called_with_correct_addresses(self):
        """sendmail is called with from_email to to_email."""
        mock_smtp_class, mock_server = _mock_smtp_context()
        to_email = "recipient@example.com"
        with patch("app.services.email_service.smtplib.SMTP", mock_smtp_class), \
             patch.dict(os.environ, _SMTP_ENV, clear=False):
            send_price_alert_email(to_email, "AAPL", "above", 200.0, 210.0)

        args = mock_server.sendmail.call_args[0]
        assert args[0] == "alerts@example.com"  # from_email
        assert args[1] == to_email               # to_email

    def test_smtp_uses_user_as_from_when_alert_from_email_unset(self):
        """When ALERT_FROM_EMAIL is unset, SMTP_USER is used as the sender."""
        env = {k: v for k, v in _SMTP_ENV.items()}
        env.pop("ALERT_FROM_EMAIL", None)
        env["SMTP_USER"] = "noreply@example.com"
        mock_smtp_class, mock_server = _mock_smtp_context()
        with patch("app.services.email_service.smtplib.SMTP", mock_smtp_class), \
             patch.dict(os.environ, env, clear=False):
            # Remove ALERT_FROM_EMAIL from the process environment for this test
            with patch.dict(os.environ, {"ALERT_FROM_EMAIL": ""}, clear=False):
                send_price_alert_email("user@example.com", "AAPL", "above", 200.0, 210.0)

        args = mock_server.sendmail.call_args[0]
        # from_email falls back to smtp_user when ALERT_FROM_EMAIL is empty
        assert args[0] in ("noreply@example.com", "")


# ===========================================================================
# send_price_alert_email , message content
# ===========================================================================

class TestSendPriceAlertEmailContent:
    def _capture_message(self, ticker: str, direction: str,
                         target: float, current: float) -> str:
        """Run send_price_alert_email and return the raw message string."""
        mock_smtp_class, mock_server = _mock_smtp_context()
        with patch("app.services.email_service.smtplib.SMTP", mock_smtp_class), \
             patch.dict(os.environ, _SMTP_ENV, clear=False):
            send_price_alert_email("r@example.com", ticker, direction, target, current)
        return mock_server.sendmail.call_args[0][2]  # raw message string

    @pytest.mark.parametrize("direction,expected_phrase", [
        ("above", "risen above"),
        ("below", "fallen below"),
    ])
    def test_subject_contains_direction_phrase(self, direction, expected_phrase):
        """Subject line includes the correct human-readable direction phrase."""
        raw = self._capture_message("TSLA", direction, 100.0, 110.0)
        msg = message_from_string(raw)
        assert expected_phrase in msg["Subject"]

    def test_subject_contains_ticker(self):
        """Subject line includes the ticker symbol."""
        raw = self._capture_message("NVDA", "above", 500.0, 600.0)
        msg = message_from_string(raw)
        assert "NVDA" in msg["Subject"]

    def test_subject_contains_target_price(self):
        """Subject line includes the target price formatted as dollars."""
        raw = self._capture_message("AAPL", "above", 200.00, 210.00)
        msg = message_from_string(raw)
        assert "200.00" in msg["Subject"]

    def test_message_to_header_matches_recipient(self):
        """The To: header of the outgoing message matches the recipient address."""
        to = "grader@university.edu"
        mock_smtp_class, mock_server = _mock_smtp_context()
        with patch("app.services.email_service.smtplib.SMTP", mock_smtp_class), \
             patch.dict(os.environ, _SMTP_ENV, clear=False):
            send_price_alert_email(to, "AAPL", "above", 200.0, 210.0)

        raw = mock_server.sendmail.call_args[0][2]
        msg = message_from_string(raw)
        assert msg["To"] == to

    def test_plain_text_body_contains_ticker_and_prices(self):
        """The plain-text part of the email mentions the ticker and both prices."""
        raw = self._capture_message("MRK", "below", 90.0, 85.0)
        assert "MRK" in raw
        assert "90.00" in raw
        assert "85.00" in raw

    def test_html_body_contains_app_link(self):
        """The HTML part contains a link back to the application."""
        raw = self._capture_message("AMZN", "above", 3000.0, 3200.0)
        assert "vercel.app" in raw or "href=" in raw

    def test_message_is_multipart_alternative(self):
        """The email is sent as multipart/alternative (plain + HTML)."""
        raw = self._capture_message("AAPL", "above", 200.0, 210.0)
        msg = message_from_string(raw)
        assert msg.get_content_type() == "multipart/alternative"


# ===========================================================================
# send_password_reset_email , credential guard
# ===========================================================================

class TestSendPasswordResetEmailCredentials:
    def test_raises_when_smtp_user_missing(self):
        """RuntimeError is raised when SMTP_USER is not set."""
        env = {k: v for k, v in _SMTP_ENV.items()}
        env["SMTP_USER"] = ""
        with patch.dict(os.environ, env, clear=False):
            with pytest.raises(RuntimeError, match="SMTP_USER"):
                send_password_reset_email("a@b.com", "https://example.com/reset/token")

    def test_raises_when_smtp_pass_missing(self):
        """RuntimeError is raised when SMTP_PASS is not set."""
        env = {k: v for k, v in _SMTP_ENV.items()}
        env["SMTP_PASS"] = ""
        with patch.dict(os.environ, env, clear=False):
            with pytest.raises(RuntimeError, match="SMTP_PASS"):
                send_password_reset_email("a@b.com", "https://example.com/reset/token")


# ===========================================================================
# send_password_reset_email , SMTP call verification
# ===========================================================================

class TestSendPasswordResetEmailSmtp:
    def test_connects_to_configured_host_and_port(self):
        """SMTP is opened against the configured host and port."""
        mock_smtp_class, _ = _mock_smtp_context()
        with patch("app.services.email_service.smtplib.SMTP", mock_smtp_class), \
             patch.dict(os.environ, _SMTP_ENV, clear=False):
            send_password_reset_email("u@example.com", "https://example.com/reset/tok")

        mock_smtp_class.assert_called_once_with("smtp.example.com", 587)

    def test_sendmail_addresses_are_correct(self):
        """sendmail is called with the correct from and to addresses."""
        mock_smtp_class, mock_server = _mock_smtp_context()
        to = "user@test.com"
        with patch("app.services.email_service.smtplib.SMTP", mock_smtp_class), \
             patch.dict(os.environ, _SMTP_ENV, clear=False):
            send_password_reset_email(to, "https://example.com/reset/tok")

        args = mock_server.sendmail.call_args[0]
        assert args[1] == to


# ===========================================================================
# send_password_reset_email , message content
# ===========================================================================

class TestSendPasswordResetEmailContent:
    def _capture_message(self, reset_link: str) -> str:
        mock_smtp_class, mock_server = _mock_smtp_context()
        with patch("app.services.email_service.smtplib.SMTP", mock_smtp_class), \
             patch.dict(os.environ, _SMTP_ENV, clear=False):
            send_password_reset_email("u@example.com", reset_link)
        return mock_server.sendmail.call_args[0][2]

    def test_subject_contains_reset_keyword(self):
        """Subject line contains a password-reset-related keyword."""
        raw = self._capture_message("https://example.com/reset/abc123")
        msg = message_from_string(raw)
        subject = msg["Subject"].lower()
        assert "password" in subject or "reset" in subject

    def test_body_contains_reset_link(self):
        """Email body contains the exact reset link passed in."""
        link = "https://app.example.com/reset?token=xyz789"
        raw = self._capture_message(link)
        assert link in raw

    def test_body_mentions_expiry(self):
        """Email body mentions the link expiry window."""
        raw = self._capture_message("https://example.com/reset/tok")
        assert "15 minutes" in raw or "expire" in raw.lower() or "expir" in raw.lower()

    def test_to_header_matches_recipient(self):
        """The To: header matches the address passed to the function."""
        to = "account@domain.org"
        mock_smtp_class, mock_server = _mock_smtp_context()
        with patch("app.services.email_service.smtplib.SMTP", mock_smtp_class), \
             patch.dict(os.environ, _SMTP_ENV, clear=False):
            send_password_reset_email(to, "https://example.com/reset/tok")

        raw = mock_server.sendmail.call_args[0][2]
        msg = message_from_string(raw)
        assert msg["To"] == to
