"""
test_alerts_logic_unit.py
Unit tests for the pure alert-trigger logic functions in app.services.alerts_logic.
No database or network dependencies; all inputs are passed directly as arguments.
"""
import pytest

from app.services.alerts_logic import is_alert_triggered, should_send_alert_email


@pytest.mark.parametrize(
    "direction,current,target,expected",
    [
        ("above", 101.0, 100.0, True),
        ("above", 100.0, 100.0, True),
        ("above", 99.9, 100.0, False),
        ("below", 99.0, 100.0, True),
        ("below", 100.0, 100.0, True),
        ("below", 100.1, 100.0, False),
        ("invalid", 100.0, 100.0, False),
    ],
)
def test_is_alert_triggered(direction, current, target, expected):
    assert is_alert_triggered(direction, current, target) is expected


@pytest.mark.parametrize(
    "alert_email_notify,user_market_alerts_enabled,expected",
    [
        (True, True, True),
        (False, True, False),
        (True, False, False),
        (False, False, False),
    ],
)
def test_should_send_alert_email(
    alert_email_notify, user_market_alerts_enabled, expected
):
    assert (
        should_send_alert_email(alert_email_notify, user_market_alerts_enabled)
        is expected
    )
