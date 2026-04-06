"""
Utility logic for evaluating and delivering price alerts.
"""


def is_alert_triggered(direction: str, current_price: float, target_price: float) -> bool:
    """
    Return True when the alert condition is satisfied.
    """
    if direction == "above":
        return current_price >= target_price
    if direction == "below":
        return current_price <= target_price
    return False


def should_send_alert_email(
    alert_email_notify: bool,
    user_market_alerts_enabled: bool,
) -> bool:
    """
    Return True only when both alert-level and market-alert user settings allow email.
    """
    return bool(alert_email_notify and user_market_alerts_enabled)
