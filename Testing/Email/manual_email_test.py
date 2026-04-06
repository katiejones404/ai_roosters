"""
Manual email testing harness for local/dev environments.

Use this script to:
1) Verify SMTP configuration is valid (send-alert, send-reset)
2) Confirm that a price-alert email arrives in a real inbox
3) Confirm that a password-reset email arrives with a working link

All commands require SMTP_USER, SMTP_PASS (and optionally SMTP_HOST,
SMTP_PORT, ALERT_FROM_EMAIL) to be set - either in the environment or
loaded from a .env file before running.
"""

from __future__ import annotations

import argparse
import os
import sys


def _configure_import_paths() -> None:
    """Make backend imports work both in Docker (/app) and local repo layout."""
    here = os.path.abspath(os.path.dirname(__file__))
    repo_root = os.path.abspath(os.path.join(here, "..", ".."))
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
# Helpers
# ---------------------------------------------------------------------------

def _check_smtp_env() -> None:
    """Print current SMTP settings (password masked) so the tester can verify."""
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = os.getenv("SMTP_PORT", "587")
    user = os.getenv("SMTP_USER", "")
    has_pass = bool(os.getenv("SMTP_PASS", ""))
    from_addr = os.getenv("ALERT_FROM_EMAIL", user or "(uses SMTP_USER)")

    print(f"smtp_host={host}")
    print(f"smtp_port={port}")
    print(f"smtp_user={user or '(not set)'}")
    print(f"smtp_pass={'***' if has_pass else '(not set)'}")
    print(f"alert_from_email={from_addr}")

    if not user or not has_pass:
        print("smtp_credentials_valid=false")
        print("hint=Set SMTP_USER and SMTP_PASS in your environment or .env file")
    else:
        print("smtp_credentials_valid=true")


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

def cmd_verify_smtp(args: argparse.Namespace) -> None:
    """Print SMTP settings, does NOT send any email."""
    _check_smtp_env()
    print("verify_complete=true")


def cmd_send_alert(args: argparse.Namespace) -> None:
    """
    Send a test price-alert email to the specified address.

    The email mimics what a real triggered alert would send.
    Check your inbox (and spam folder) to confirm delivery.
    """
    _check_smtp_env()
    print(f"sending_alert_email_to={args.email}")
    print(f"ticker={args.ticker.upper()}")
    print(f"direction={args.direction}")
    print(f"target_price={args.target_price}")
    print(f"current_price={args.current_price}")

    try:
        send_price_alert_email(
            to_email=args.email,
            ticker=args.ticker.upper(),
            direction=args.direction,
            target_price=float(args.target_price),
            current_price=float(args.current_price),
        )
        print("send_result=success")
        print("next_step=Check the inbox for the alert email.")
    except RuntimeError as e:
        print(f"send_result=error_credentials")
        print(f"error={e}")
    except Exception as e:
        print(f"send_result=error_smtp")
        print(f"error={e}")


def cmd_send_reset(args: argparse.Namespace) -> None:
    """
    Send a test password-reset email to the specified address.

    Uses a dummy reset link, follow the link in the email to confirm it is
    present and formatted correctly.
    """
    _check_smtp_env()
    reset_link = args.reset_link or "https://ai-roosters-webpage.vercel.app/reset-password?token=TEST_TOKEN_123"
    print(f"sending_reset_email_to={args.email}")
    print(f"reset_link={reset_link}")

    try:
        send_password_reset_email(
            to_email=args.email,
            reset_link=reset_link,
        )
        print("send_result=success")
        print("next_step=Check the inbox for the password-reset email.")
    except RuntimeError as e:
        print(f"send_result=error_credentials")
        print(f"error={e}")
    except Exception as e:
        print(f"send_result=error_smtp")
        print(f"error={e}")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manual email testing harness, verifies SMTP config and sends test emails."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # verify-smtp: print settings, no email sent
    verify = sub.add_parser("verify-smtp", help="Print SMTP settings (no email sent)")
    verify.set_defaults(func=cmd_verify_smtp)

    # send-alert: send a test price-alert email
    alert_cmd = sub.add_parser("send-alert", help="Send a test price-alert email")
    alert_cmd.add_argument("--email", required=True, help="Recipient email address")
    alert_cmd.add_argument("--ticker", default="AAPL", help="Stock ticker (default: AAPL)")
    alert_cmd.add_argument(
        "--direction",
        choices=["above", "below"],
        default="above",
        help="Alert direction (default: above)",
    )
    alert_cmd.add_argument(
        "--target-price",
        type=float,
        default=200.0,
        help="Alert target price (default: 200.0)",
    )
    alert_cmd.add_argument(
        "--current-price",
        type=float,
        default=210.0,
        help="Simulated current price (default: 210.0)",
    )
    alert_cmd.set_defaults(func=cmd_send_alert)

    # send-reset: send a test password-reset email
    reset_cmd = sub.add_parser("send-reset", help="Send a test password-reset email")
    reset_cmd.add_argument("--email", required=True, help="Recipient email address")
    reset_cmd.add_argument(
        "--reset-link",
        default="",
        help="Reset URL to embed (default: dummy Vercel URL with TEST_TOKEN_123)",
    )
    reset_cmd.set_defaults(func=cmd_send_reset)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
