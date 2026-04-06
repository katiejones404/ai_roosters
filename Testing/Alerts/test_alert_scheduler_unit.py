"""
test_alert_scheduler_unit.py
Unit tests for app.services.alert_scheduler.run_alert_checks.

Notes
-----
The SQLAlchemy engine and session are patched so no live database is needed.
Email sending is also patched to avoid SMTP configuration requirements.
Tests verify trigger logic, deactivation, email dispatch, and skip conditions.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call, ANY

import pytest


# ---------------------------------------------------------------------------
# Import path setup
# ---------------------------------------------------------------------------

def _configure_import_paths() -> None:
    here = os.path.abspath(os.path.dirname(__file__))
    repo_root = os.path.abspath(os.path.join(here, "..", ".."))
    backend_root = os.path.join(repo_root, "backend")
    for candidate in ("/app", backend_root, repo_root):
        if os.path.isdir(candidate) and candidate not in sys.path:
            sys.path.insert(0, candidate)


_configure_import_paths()

from app.services.alert_scheduler import run_alert_checks  # noqa: E402


# ---------------------------------------------------------------------------
# Test-object factories
# ---------------------------------------------------------------------------

def _make_user(
    email: str = "user@example.com",
    market_alerts_enabled: bool = True,
) -> MagicMock:
    """Return a mock User with notification preferences."""
    user = MagicMock()
    user.email = email
    user.notify_market_alerts_enabled = market_alerts_enabled
    return user


def _make_alert(
    ticker: str = "AAPL",
    target_price: float = 200.0,
    direction: str = "above",
    email_notify: bool = True,
    user: MagicMock | None = None,
) -> MagicMock:
    """Return a mock PriceAlert with is_active=True."""
    alert = MagicMock()
    alert.ticker = ticker
    alert.target_price = target_price
    alert.direction = direction
    alert.email_notify = email_notify
    alert.is_active = True
    alert.triggered_at = None
    alert.user = user if user is not None else _make_user()
    return alert


def _setup_mocks(alerts: list, price_rows: list):
    """
    Patch create_engine and sessionmaker to return a fake session.

    Returns (mock_db, mock_engine_patch, mock_sessionmaker_patch) ready for
    use in a `with` block, but callers receive them via yield from the fixture.
    """
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.all.return_value = alerts
    mock_db.execute.return_value.fetchall.return_value = price_rows

    mock_engine = MagicMock()
    mock_session_class = MagicMock(return_value=mock_db)
    mock_sessionmaker = MagicMock(return_value=mock_session_class)

    return mock_db, mock_engine, mock_sessionmaker


# ---------------------------------------------------------------------------
# Early-exit: no active alerts
# ---------------------------------------------------------------------------

class TestNoActiveAlerts:
    def test_returns_early_when_no_alerts(self):
        """run_alert_checks commits nothing when there are no active alerts."""
        mock_db, mock_engine, mock_sm = _setup_mocks([], [])

        with patch("app.services.alert_scheduler.create_engine", return_value=mock_engine), \
             patch("app.services.alert_scheduler.sessionmaker", mock_sm), \
             patch("app.services.alert_scheduler.send_price_alert_email") as mock_email:
            run_alert_checks()

        mock_email.assert_not_called()
        mock_db.commit.assert_not_called()


# ---------------------------------------------------------------------------
# Alert triggered: deactivation
# ---------------------------------------------------------------------------

class TestAlertDeactivation:
    def test_triggered_alert_is_deactivated(self):
        """An alert whose condition is met is set inactive and given a triggered_at timestamp."""
        alert = _make_alert(ticker="AAPL", target_price=200.0, direction="above")
        price_rows = [("AAPL", 210.0)]  # current > target = triggers
        mock_db, mock_engine, mock_sm = _setup_mocks([alert], price_rows)

        with patch("app.services.alert_scheduler.create_engine", return_value=mock_engine), \
             patch("app.services.alert_scheduler.sessionmaker", mock_sm), \
             patch("app.services.alert_scheduler.send_price_alert_email"):
            run_alert_checks()

        assert alert.is_active is False
        assert alert.triggered_at is not None

    def test_triggered_at_is_a_datetime(self):
        """triggered_at is set to a UTC datetime after triggering."""
        alert = _make_alert(ticker="TSLA", target_price=100.0, direction="below")
        price_rows = [("TSLA", 90.0)]  # current < target = triggers
        mock_db, mock_engine, mock_sm = _setup_mocks([alert], price_rows)

        with patch("app.services.alert_scheduler.create_engine", return_value=mock_engine), \
             patch("app.services.alert_scheduler.sessionmaker", mock_sm), \
             patch("app.services.alert_scheduler.send_price_alert_email"):
            run_alert_checks()

        assert isinstance(alert.triggered_at, datetime)

    def test_untriggered_alert_stays_active(self):
        """An alert whose condition is NOT met remains active."""
        alert = _make_alert(ticker="AAPL", target_price=200.0, direction="above")
        price_rows = [("AAPL", 190.0)]  # current < target = does NOT trigger
        mock_db, mock_engine, mock_sm = _setup_mocks([alert], price_rows)

        with patch("app.services.alert_scheduler.create_engine", return_value=mock_engine), \
             patch("app.services.alert_scheduler.sessionmaker", mock_sm), \
             patch("app.services.alert_scheduler.send_price_alert_email") as mock_email:
            run_alert_checks()

        assert alert.is_active is True
        assert alert.triggered_at is None
        mock_email.assert_not_called()

    def test_db_commit_called_after_processing(self):
        """db.commit() is called once after all alerts are processed."""
        alert = _make_alert(ticker="AAPL", target_price=200.0, direction="above")
        price_rows = [("AAPL", 210.0)]
        mock_db, mock_engine, mock_sm = _setup_mocks([alert], price_rows)

        with patch("app.services.alert_scheduler.create_engine", return_value=mock_engine), \
             patch("app.services.alert_scheduler.sessionmaker", mock_sm), \
             patch("app.services.alert_scheduler.send_price_alert_email"):
            run_alert_checks()

        mock_db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# Email dispatch
# ---------------------------------------------------------------------------

class TestEmailDispatch:
    def test_email_sent_when_all_notifications_enabled(self):
        """Email is sent when alert.email_notify and market-alert preference is True."""
        user = _make_user(email="test@example.com", market_alerts_enabled=True)
        alert = _make_alert(ticker="NVDA", target_price=500.0, direction="above",
                            email_notify=True, user=user)
        price_rows = [("NVDA", 600.0)]
        mock_db, mock_engine, mock_sm = _setup_mocks([alert], price_rows)

        with patch("app.services.alert_scheduler.create_engine", return_value=mock_engine), \
             patch("app.services.alert_scheduler.sessionmaker", mock_sm), \
             patch("app.services.alert_scheduler.send_price_alert_email") as mock_email:
            run_alert_checks()

        mock_email.assert_called_once_with(
            to_email="test@example.com",
            ticker="NVDA",
            direction="above",
            target_price=500.0,
            current_price=600.0,
        )

    def test_email_not_sent_when_alert_email_notify_false(self):
        """Email is suppressed when alert.email_notify is False, even if user settings allow."""
        user = _make_user(market_alerts_enabled=True)
        alert = _make_alert(ticker="AAPL", target_price=200.0, direction="above",
                            email_notify=False, user=user)
        price_rows = [("AAPL", 210.0)]
        mock_db, mock_engine, mock_sm = _setup_mocks([alert], price_rows)

        with patch("app.services.alert_scheduler.create_engine", return_value=mock_engine), \
             patch("app.services.alert_scheduler.sessionmaker", mock_sm), \
             patch("app.services.alert_scheduler.send_price_alert_email") as mock_email:
            run_alert_checks()

        mock_email.assert_not_called()
        assert alert.is_active is False  # still deactivated

    def test_email_not_sent_when_market_alerts_disabled(self):
        """Email is suppressed when the user has turned off market alert emails."""
        user = _make_user(market_alerts_enabled=False)
        alert = _make_alert(ticker="AMD", target_price=100.0, direction="below",
                            email_notify=True, user=user)
        price_rows = [("AMD", 90.0)]
        mock_db, mock_engine, mock_sm = _setup_mocks([alert], price_rows)

        with patch("app.services.alert_scheduler.create_engine", return_value=mock_engine), \
             patch("app.services.alert_scheduler.sessionmaker", mock_sm), \
             patch("app.services.alert_scheduler.send_price_alert_email") as mock_email:
            run_alert_checks()

        mock_email.assert_not_called()
        assert alert.is_active is False

    def test_email_failure_does_not_prevent_alert_deactivation(self):
        """
        If send_price_alert_email raises an exception, the alert is still deactivated
        and db.commit() is still called so the run does not lose other processed alerts.
        """
        user = _make_user(market_alerts_enabled=True)
        alert = _make_alert(ticker="COIN", target_price=50.0, direction="above",
                            email_notify=True, user=user)
        price_rows = [("COIN", 60.0)]
        mock_db, mock_engine, mock_sm = _setup_mocks([alert], price_rows)

        with patch("app.services.alert_scheduler.create_engine", return_value=mock_engine), \
             patch("app.services.alert_scheduler.sessionmaker", mock_sm), \
             patch("app.services.alert_scheduler.send_price_alert_email",
                   side_effect=Exception("SMTP timeout")):
            run_alert_checks()

        assert alert.is_active is False
        mock_db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# Skip conditions
# ---------------------------------------------------------------------------

class TestSkipConditions:
    def test_alert_skipped_when_ticker_has_no_price(self):
        """Alerts are skipped when no price row exists for that ticker."""
        alert = _make_alert(ticker="FAKE", target_price=100.0, direction="above")
        price_rows = []  # no prices at all
        mock_db, mock_engine, mock_sm = _setup_mocks([alert], price_rows)

        with patch("app.services.alert_scheduler.create_engine", return_value=mock_engine), \
             patch("app.services.alert_scheduler.sessionmaker", mock_sm), \
             patch("app.services.alert_scheduler.send_price_alert_email") as mock_email:
            run_alert_checks()

        mock_email.assert_not_called()
        assert alert.is_active is True  # unchanged

    def test_alert_skipped_when_user_is_none(self):
        """Alerts with no associated user record are silently skipped."""
        alert = _make_alert(ticker="AAPL", target_price=200.0, direction="above")
        alert.user = None
        price_rows = [("AAPL", 210.0)]
        mock_db, mock_engine, mock_sm = _setup_mocks([alert], price_rows)

        with patch("app.services.alert_scheduler.create_engine", return_value=mock_engine), \
             patch("app.services.alert_scheduler.sessionmaker", mock_sm), \
             patch("app.services.alert_scheduler.send_price_alert_email") as mock_email:
            run_alert_checks()

        mock_email.assert_not_called()

    def test_multiple_alerts_processed_independently(self):
        """Each alert is evaluated independently; one skip does not block others."""
        user = _make_user(email="multi@example.com", market_alerts_enabled=True)

        alert_hit = _make_alert(ticker="AAPL", target_price=200.0, direction="above",
                                email_notify=True, user=user)
        alert_miss = _make_alert(ticker="TSLA", target_price=400.0, direction="above",
                                 email_notify=True, user=user)

        price_rows = [
            ("AAPL", 210.0),  # triggers
            ("TSLA", 350.0),  # does NOT trigger (below target)
        ]
        mock_db, mock_engine, mock_sm = _setup_mocks([alert_hit, alert_miss], price_rows)

        with patch("app.services.alert_scheduler.create_engine", return_value=mock_engine), \
             patch("app.services.alert_scheduler.sessionmaker", mock_sm), \
             patch("app.services.alert_scheduler.send_price_alert_email") as mock_email:
            run_alert_checks()

        mock_email.assert_called_once()
        assert alert_hit.is_active is False
        assert alert_miss.is_active is True


# ---------------------------------------------------------------------------
# Direction boundary cases (at-target price)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("direction,current,target,should_trigger", [
    ("above", 200.0, 200.0, True),   # exactly at target = triggers
    ("above", 199.99, 200.0, False), # just below target = no trigger
    ("below", 100.0, 100.0, True),   # exactly at target = triggers
    ("below", 100.01, 100.0, False), # just above target = no trigger
])
def test_direction_boundary_triggers(direction, current, target, should_trigger):
    """Alert trigger respects exact boundary: >= for above, <= for below."""
    user = _make_user(market_alerts_enabled=True)
    alert = _make_alert(ticker="TEST", target_price=target, direction=direction,
                        email_notify=True, user=user)
    price_rows = [("TEST", current)]
    mock_db, mock_engine, mock_sm = _setup_mocks([alert], price_rows)

    with patch("app.services.alert_scheduler.create_engine", return_value=mock_engine), \
         patch("app.services.alert_scheduler.sessionmaker", mock_sm), \
         patch("app.services.alert_scheduler.send_price_alert_email") as mock_email:
        run_alert_checks()

    if should_trigger:
        assert alert.is_active is False
        mock_email.assert_called_once()
    else:
        assert alert.is_active is True
        mock_email.assert_not_called()
