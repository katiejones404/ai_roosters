"""
Manual alert testing harness for local/dev environments.

Use this script to:
1) Create a test user and alert
2) Seed/update a dummy stock price
3) Run the alert checker once
4) Verify whether the alert triggered
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import create_engine, text


def _configure_import_paths() -> None:
    """
    Make backend imports work both in Docker (/app) and local repo layout.
    """
    here = os.path.abspath(os.path.dirname(__file__))
    repo_root = os.path.abspath(os.path.join(here, "..", ".."))
    backend_root = os.path.join(repo_root, "backend")

    for candidate in ("/app", backend_root, repo_root):
        if os.path.isdir(candidate) and candidate not in sys.path:
            sys.path.insert(0, candidate)


_configure_import_paths()

from app.core.security import hash_password  # noqa: E402
from app.services.alert_scheduler import run_alert_checks  # noqa: E402


def _database_url() -> str:
    testing_url = os.getenv("DATABASE_URL_TESTING", "").strip()
    if testing_url:
        return testing_url
    return os.getenv(
        "DATABASE_URL",
        "postgresql://stock_user:stock_pass@postgres:5432/stock_db",
    )


def _engine():
    return create_engine(_database_url())


def _safe_username_from_email(email: str) -> str:
    local = email.split("@", 1)[0].lower()
    local = re.sub(r"[^a-z0-9_]", "_", local)[:20]
    if not local:
        local = "alert_test_user"
    return f"{local}_{uuid.uuid4().hex[:6]}"


def ensure_test_user(email: str, force_enable_notifications: bool = False) -> str:
    email = email.lower().strip()
    with _engine().begin() as conn:
        row = conn.execute(
            text("SELECT id FROM users WHERE email = :email LIMIT 1"),
            {"email": email},
        ).fetchone()
        if row:
            user_id = str(row[0])
            if force_enable_notifications:
                conn.execute(
                    text(
                        """
                        UPDATE users
                        SET notify_market_alerts_enabled = TRUE
                        WHERE id = :user_id
                        """
                    ),
                    {"user_id": user_id},
                )
            return user_id

        user_id = str(uuid.uuid4())
        username = _safe_username_from_email(email)
        password_hash = hash_password("AlertTest123!")
        conn.execute(
            text(
                """
                INSERT INTO users (
                    id,
                    username,
                    email,
                    password_hash,
                    notify_market_alerts_enabled,
                    notify_push_enabled
                )
                VALUES (
                    :id,
                    :username,
                    :email,
                    :password_hash,
                    TRUE,
                    FALSE
                )
                """
            ),
            {
                "id": user_id,
                "username": username,
                "email": email,
                "password_hash": password_hash,
            },
        )
        return user_id


def set_latest_stock_price(ticker: str, price: float) -> None:
    ticker = ticker.upper().strip()
    today = date.today()
    with _engine().begin() as conn:
        updated = conn.execute(
            text(
                """
                UPDATE stocks
                SET close = :price,
                    adjusted_close = :price,
                    open = COALESCE(open, :price),
                    high = GREATEST(COALESCE(high, :price), :price),
                    low = LEAST(COALESCE(low, :price), :price),
                    created_at = NOW()
                WHERE ticker = :ticker
                  AND date = :today
                """
            ),
            {"ticker": ticker, "today": today, "price": price},
        )
        if updated.rowcount and updated.rowcount > 0:
            return

        conn.execute(
            text(
                """
                INSERT INTO stocks (
                    ticker, date, adjusted_close, open, high, low, close, volume,
                    return_1d, return_30d, return_120d, return_360d, created_at
                )
                VALUES (
                    :ticker, :today, :price, :price, :price, :price, :price, 0,
                    NULL, NULL, NULL, NULL, NOW()
                )
                """
            ),
            {"ticker": ticker, "today": today, "price": price},
        )


def create_test_alert(
    user_id: str,
    ticker: str,
    target_price: float,
    direction: str,
    email_notify: bool,
) -> str:
    ticker = ticker.upper().strip()
    direction = direction.lower().strip()
    if direction not in ("above", "below"):
        raise ValueError("direction must be 'above' or 'below'")

    with _engine().begin() as conn:
        conn.execute(
            text(
                """
                UPDATE price_alerts
                SET is_active = FALSE
                WHERE user_id = :user_id
                  AND ticker = :ticker
                  AND is_active = TRUE
                """
            ),
            {"user_id": user_id, "ticker": ticker},
        )

        alert_id = str(uuid.uuid4())
        conn.execute(
            text(
                """
                INSERT INTO price_alerts (
                    id, user_id, ticker, target_price, direction,
                    is_active, email_notify, triggered_at, created_at
                )
                VALUES (
                    :id, :user_id, :ticker, :target_price, :direction,
                    TRUE, :email_notify, NULL, :created_at
                )
                """
            ),
            {
                "id": alert_id,
                "user_id": user_id,
                "ticker": ticker,
                "target_price": target_price,
                "direction": direction,
                "email_notify": email_notify,
                "created_at": datetime.now(timezone.utc),
            },
        )
        return alert_id


def get_alert_status(alert_id: str) -> dict[str, str]:
    with _engine().begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT id, ticker, target_price, direction, is_active, email_notify, triggered_at
                FROM price_alerts
                WHERE id = :alert_id
                LIMIT 1
                """
            ),
            {"alert_id": alert_id},
        ).fetchone()
        if not row:
            return {"error": f"Alert {alert_id} not found"}

        return {
            "id": str(row[0]),
            "ticker": str(row[1]),
            "target_price": str(row[2]),
            "direction": str(row[3]),
            "is_active": str(row[4]),
            "email_notify": str(row[5]),
            "triggered_at": "" if row[6] is None else str(row[6]),
        }


def get_latest_stock_price(ticker: str) -> str:
    ticker = ticker.upper().strip()
    with _engine().begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT date, close
                FROM stocks
                WHERE ticker = :ticker AND close IS NOT NULL
                ORDER BY date DESC
                LIMIT 1
                """
            ),
            {"ticker": ticker},
        ).fetchone()
        if not row:
            return "N/A"
        return f"{row[1]} (date={row[0]})"


def cleanup_test_data(email: str, ticker: str, delete_user: bool) -> None:
    ticker = ticker.upper().strip()
    email = email.lower().strip()
    with _engine().begin() as conn:
        row = conn.execute(
            text("SELECT id FROM users WHERE email = :email LIMIT 1"),
            {"email": email},
        ).fetchone()
        if not row:
            conn.execute(
                text("DELETE FROM stocks WHERE ticker = :ticker"),
                {"ticker": ticker},
            )
            return

        user_id = str(row[0])
        conn.execute(
            text("DELETE FROM price_alerts WHERE user_id = :user_id AND ticker = :ticker"),
            {"user_id": user_id, "ticker": ticker},
        )
        conn.execute(
            text("DELETE FROM stocks WHERE ticker = :ticker"),
            {"ticker": ticker},
        )
        if delete_user:
            conn.execute(text("DELETE FROM users WHERE id = :user_id"), {"user_id": user_id})


def cmd_setup(args: argparse.Namespace) -> None:
    user_id = ensure_test_user(
        args.email,
        force_enable_notifications=args.force_enable_notifications,
    )
    start_price = args.start_price
    if start_price is None:
        if args.direction == "above":
            start_price = max(0.01, args.target_price - 5.0)
        else:
            start_price = args.target_price + 5.0

    set_latest_stock_price(args.ticker, float(start_price))
    alert_id = create_test_alert(
        user_id=user_id,
        ticker=args.ticker,
        target_price=float(args.target_price),
        direction=args.direction,
        email_notify=(not args.no_email_notify),
    )
    print(f"user_id={user_id}")
    print(f"alert_id={alert_id}")
    print(f"ticker={args.ticker.upper()}")
    print(f"current_price={get_latest_stock_price(args.ticker)}")
    print("setup_complete=true")


def cmd_set_price(args: argparse.Namespace) -> None:
    set_latest_stock_price(args.ticker, float(args.price))
    print(f"ticker={args.ticker.upper()}")
    print(f"current_price={get_latest_stock_price(args.ticker)}")


def cmd_run_check(_: argparse.Namespace) -> None:
    run_alert_checks()
    print("run_alert_checks_complete=true")


def cmd_status(args: argparse.Namespace) -> None:
    if args.alert_id:
        status = get_alert_status(args.alert_id)
        for key, value in status.items():
            print(f"{key}={value}")
        return

    print(f"ticker={args.ticker.upper()}")
    print(f"current_price={get_latest_stock_price(args.ticker)}")


def cmd_cleanup(args: argparse.Namespace) -> None:
    cleanup_test_data(args.email, args.ticker, args.delete_user)
    print("cleanup_complete=true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manual alert testing harness")
    sub = parser.add_subparsers(dest="command", required=True)

    setup = sub.add_parser("setup", help="Create test user + alert + initial stock price")
    setup.add_argument("--email", required=True, help="Test user email")
    setup.add_argument("--ticker", default="ALRTT", help="Dummy ticker symbol")
    setup.add_argument("--target-price", type=float, default=100.0, help="Alert target price")
    setup.add_argument(
        "--direction",
        choices=["above", "below"],
        default="above",
        help="Alert direction",
    )
    setup.add_argument(
        "--start-price",
        type=float,
        default=None,
        help="Initial stock close price before triggering",
    )
    setup.add_argument(
        "--no-email-notify",
        action="store_true",
        help="Create alert with email_notify=false",
    )
    setup.add_argument(
        "--force-enable-notifications",
        action="store_true",
        help="Force-enable user market alert preference for testing sends",
    )
    setup.set_defaults(func=cmd_setup)

    set_price = sub.add_parser("set-price", help="Set/overwrite latest stock close price")
    set_price.add_argument("--ticker", default="ALRTT", help="Ticker symbol")
    set_price.add_argument("--price", required=True, type=float, help="Close price to set")
    set_price.set_defaults(func=cmd_set_price)

    run_check = sub.add_parser("run-check", help="Run backend alert checker once")
    run_check.set_defaults(func=cmd_run_check)

    status = sub.add_parser("status", help="Show alert and stock status")
    status.add_argument("--alert-id", default="", help="Specific alert id to inspect")
    status.add_argument("--ticker", default="ALRTT", help="Ticker symbol")
    status.set_defaults(func=cmd_status)

    cleanup = sub.add_parser("cleanup", help="Remove test alert + ticker rows")
    cleanup.add_argument("--email", required=True, help="Test user email")
    cleanup.add_argument("--ticker", default="ALRTT", help="Ticker symbol")
    cleanup.add_argument(
        "--delete-user",
        action="store_true",
        help="Also delete the test user record",
    )
    cleanup.set_defaults(func=cmd_cleanup)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
