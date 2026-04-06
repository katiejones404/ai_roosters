# Email Manual Test Kit

This folder tests the two email functions in StockSense:

1. **Price-alert email** - sent when a price alert triggers
2. **Password-reset email** - sent when a user requests a password reset

## What It Tests

- SMTP configuration is valid (host, port, credentials reachable)
- Price-alert email arrives with correct ticker, direction, and prices
- Password-reset email arrives with the expected reset link
- Subject lines contain the right human-readable phrases

## Prerequisites

1. `docker compose up -d api`
2. Root `.env` must contain SMTP settings:
   - `SMTP_HOST` (e.g. `smtp.gmail.com`)
   - `SMTP_PORT` (e.g. `587`)
   - `SMTP_USER` (Gmail address or SMTP username)
   - `SMTP_PASS` (App password - not your Google account password)
   - `ALERT_FROM_EMAIL` (optional; defaults to `SMTP_USER`)

## Quick Tests (PowerShell)

From the `ai_roosters/` folder:

### Step 1 - Verify SMTP config (no email sent)

```powershell
.\Testing\Email\run_email_test.ps1 -Action verify-smtp
```

Expected output:
```
smtp_host=smtp.gmail.com
smtp_user=your@gmail.com
smtp_pass=***
smtp_credentials_valid=true
verify_complete=true
```

### Step 2 - Send a test price-alert email

```powershell
.\Testing\Email\run_email_test.ps1 -Action send-alert -Email "your@email.com" -Ticker AAPL -Direction above -TargetPrice 200 -CurrentPrice 210
```

Expected:
- `send_result=success`
- An email arrives with subject: **"StockSense Alert: AAPL has risen above $200.00"**

### Step 3 - Send a test password-reset email

```powershell
.\Testing\Email\run_email_test.ps1 -Action send-reset -Email "your@email.com"
```

Expected:
- `send_result=success`
- An email arrives with a reset link in the body and a 15-minute expiry note

## Direct Script Usage (inside API container)

```powershell
docker compose exec api python /app/Testing/Email/manual_email_test.py verify-smtp
docker compose exec api python /app/Testing/Email/manual_email_test.py send-alert --email you@example.com --ticker NVDA --direction above --target-price 500 --current-price 600
docker compose exec api python /app/Testing/Email/manual_email_test.py send-reset --email you@example.com
```

## Unit Tests (no SMTP required)

Unit tests for both email functions live in `Testing/Email/unit/test_email_service_unit.py`.
They mock the SMTP connection and verify message content entirely offline.

Run them with:

```powershell
.\run_testing.ps1 Testing/Email
```

or from the repo root:

```powershell
python -m pytest Testing/Email -v
```

## Notes

- Gmail requires an **App Password** (not your account password). Generate one at:
  `Google Account -> Security -> 2-Step Verification -> App passwords`
- Check your spam folder if the test email does not appear in your inbox.
- The reset link in the test email points to `TEST_TOKEN_123`; it is not a real
  working reset link - only the email delivery itself is being verified.
