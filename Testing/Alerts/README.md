# Alerts Manual Test Kit

This folder lets you test price alerts end-to-end with a dummy stock row that you can change at will.

## What It Tests

- Creating a test alert in price_alerts
- Creating/updating a dummy stock price in stocks
- Running the backend alert checker once
- Confirming that the alert was triggered
- Confirming email behavior based on settings

## Prerequisites

1. `docker compose up -d api frontend` 
   - Run this command on its own if using neon url in .env file, there needs to be a pause in between commands.
2. Root `.env` contains SMTP settings:
   - `SMTP_HOST`
   - `SMTP_PORT`
   - `SMTP_USER`
   - `SMTP_PASS`
   - `ALERT_FROM_EMAIL`
3. Optional testing DB override (recommended):
   - Set `DATABASE_URL_TESTING` in your shell (local postgres db), or
   - Store it in `.env` and load it before running tests.

If `DATABASE_URL_TESTING` is set, this test uses that instead of `DATABASE_URL`.

## Quick Test (PowerShell)

From repo root (ai_roosters):

```powershell
# Optional: keep production DATABASE_URL untouched
$env:DATABASE_URL_TESTING="postgresql://stock_user:stock_pass@postgres:5432/stock_db"
```

```powershell
.\Testing\Alerts\run_alert_test.ps1 -Action setup -Email "airooster492@gmail.com" -Ticker "ALRTT" -TargetPrice 100 -Direction above
.\Testing\Alerts\run_alert_test.ps1 -Action set-price -Ticker "ALRTT" -Price 120
.\Testing\Alerts\run_alert_test.ps1 -Action run-check
.\Testing\Alerts\run_alert_test.ps1 -Action status -Ticker "ALRTT"
```

## Verified No-Email Test (Notifications Off in Settings)

If the user has Email Notifications turned off in Settings, this flow should trigger the alert but not send email.

```powershell
docker-compose up -d api
.\Testing\Alerts\run_alert_test.ps1 -Action setup -Email "airooster492@gmail.com" -Ticker "ALRNO" -TargetPrice 100 -Direction above
.\Testing\Alerts\run_alert_test.ps1 -Action set-price -Ticker "ALRNO" -Price 120
.\Testing\Alerts\run_alert_test.ps1 -Action run-check
docker compose logs --tail 200 api | Select-String -Pattern "ALRNO|Alert email sent|email disabled"
```

Expected verification line in logs:

```text
INFO:startup:Alert triggered (email disabled by alert/user preferences): ALRNO above 100.0
```

If you see that line and no new inbox email, behavior is correct.

Optional status/cleanup:

```powershell
.\Testing\Alerts\run_alert_test.ps1 -Action status -Ticker "ALRTT"
.\Testing\Alerts\run_alert_test.ps1 -Action cleanup -Email "airooster492@gmail.com" -Ticker "ALRTT"
```

## Direct Script Usage

You can also call the script directly in the API container:

```powershell
docker compose exec api python /app/Testing/Alerts/manual_alert_test.py setup --email airooster492@gmail.com --ticker ALRTT --target-price 100 --direction above
docker compose exec api python /app/Testing/Alerts/manual_alert_test.py set-price --ticker ALRTT --price 120
docker compose exec api python /app/Testing/Alerts/manual_alert_test.py run-check
```

## Notes

- ALRTT is a dummy ticker for testing only.
- The test creates a user record if the email does not exist.
- For existing users, setup preserves current notification settings by default.
- To force-enable user notification settings for send-path testing, use `--force-enable-notifications`.
- If you disable email/market alerts in settings, alert records can still trigger, but email should not be sent.
