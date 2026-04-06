"""
Notes - Background job for processing active price alerts.
Checks latest stock prices, triggers alerts, and sends emails when conditions are met.
"""

import logging
import os
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.models.models import PriceAlert
from app.services.alerts_logic import is_alert_triggered, should_send_alert_email
from app.services.email_service import send_price_alert_email

logger = logging.getLogger("startup")


def run_alert_checks() -> None:
    """Check all active price alerts against latest stock prices and email on trigger."""
    db_url = os.getenv("DATABASE_URL", "postgresql://stock_user:stock_pass@postgres:5432/stock_db")
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        alerts = db.query(PriceAlert).filter(PriceAlert.is_active == True).all()  # noqa: E712
        if not alerts:
            return

        tickers = list({a.ticker for a in alerts})
        rows = db.execute(
            text(
                "SELECT DISTINCT ON (ticker) ticker, close FROM stocks "
                "WHERE ticker = ANY(:tickers) AND close IS NOT NULL "
                "ORDER BY ticker, date DESC"
            ),
            {"tickers": tickers},
        ).fetchall()
        latest_prices = {row[0]: float(row[1]) for row in rows}

        for alert in alerts:
            current = latest_prices.get(alert.ticker)
            if current is None or not alert.user:
                continue

            target = float(alert.target_price)
            triggered = is_alert_triggered(alert.direction, current, target)
            if not triggered:
                continue

            user_market_alerts_enabled = bool(
                True
                if alert.user.notify_market_alerts_enabled is None
                else alert.user.notify_market_alerts_enabled
            )

            if should_send_alert_email(
                alert.email_notify,
                user_market_alerts_enabled,
            ):
                try:
                    send_price_alert_email(
                        to_email=alert.user.email,
                        ticker=alert.ticker,
                        direction=alert.direction,
                        target_price=target,
                        current_price=current,
                    )
                    logger.info("Alert email sent: %s %s %s", alert.ticker, alert.direction, target)
                except Exception as email_err:
                    logger.warning("Alert email failed for %s: %s", alert.ticker, email_err)
            else:
                logger.info(
                    "Alert triggered (email disabled by alert/user preferences): %s %s %s",
                    alert.ticker,
                    alert.direction,
                    target,
                )

            alert.is_active = False
            alert.triggered_at = datetime.now(timezone.utc)

        db.commit()
    except Exception as e:
        logger.error("Alert check failed: %s", e, exc_info=True)
    finally:
        db.close()
        engine.dispose()
