# Testing
This folder contains unit and behavioral tests for every backend module.

---

## How to Run Tests

### Unit Tests (run locally)

Unit tests use no real database or HTTP server,all dependencies are mocked.

```bash
# From ai_roosters/backend/
cd ai_roosters/backend

python -m pytest \
  ../Testing/Alerts/test_alerts_logic_unit.py \
  ../Testing/Alerts/test_alert_scheduler_unit.py \
  ../Testing/Email/unit/test_email_service_unit.py \
  ../Testing/News/unit/test_news_unit.py \
  ../Testing/Networth/unit/test_networth_unit.py \
  ../Testing/Portfolio/unit/test_portfolio_service_unit.py \
  ../Testing/Sentiment/unit/test_sentiment_logic_unit.py \
  ../Testing/Stocks/unit/test_price_ingest.py \
  ../Testing/User/unit/test_security_unit.py \
  ../Testing/User/unit/test_user_model.py \
  -v
```

**Expected: 250 passed**

---

### Behavioral Tests (run in Docker)

Behavioral tests use FastAPI `TestClient` + SQLite in-memory databases to test full HTTP request/response cycles. They require the project's Docker environment (Python 3.11 + Pydantic v2).

```bash
# From ai_roosters/
docker compose up -d

# Run all behavioral tests inside the container
docker compose exec api python -m pytest \
  ./Testing/Alerts/behavioral/test_alerts_behavioral.py \
  ./Testing/Email/behavioral/test_email_behavioral.py \
  ./Testing/Networth/behavioral/test_networth_behavioral.py \
  ./Testing/News/behavioral/test_news_behavioral.py \
  ./Testing/Portfolio/behavioral/test_portfolio_behavioral.py \
  ./Testing/User/behavioral/test_auth_endpoints.py \
  ./Testing/Stocks/behavior/test_stocks_api.py \
  -v
```

---

## Test Coverage by Module

| Module | Unit Tests | Behavioral Tests | Notes |
|--------|-----------|-----------------|-------|
| **Alerts** | `Alerts/test_alerts_logic_unit.py`<br>`Alerts/test_alert_scheduler_unit.py` | `Alerts/behavioral/test_alerts_behavioral.py` | Logic + scheduler + API |
| **Email** | `Email/unit/test_email_service_unit.py` | `Email/behavioral/test_email_behavioral.py` | SMTP mocked in unit tests |
| **News** | `News/unit/test_news_unit.py` | `News/behavioral/test_news_behavioral.py` | Sentiment normalization, aggregation |
| **Networth** | `Networth/unit/test_networth_unit.py` | `Networth/behavioral/test_networth_behavioral.py` | Assets, liabilities, snapshots |
| **Portfolio** | `Portfolio/unit/test_portfolio_service_unit.py` | `Portfolio/behavioral/test_portfolio_behavioral.py` | CRUD, weighted average price |
| **Sentiment** | `Sentiment/unit/test_sentiment_logic_unit.py` |  | `label_from_return`, ticker ordering |
| **Stocks** | `Stocks/unit/test_price_ingest.py` | `Stocks/behavior/test_stocks_api.py` | yfinance ingest, batch store |
| **User** | `User/unit/test_security_unit.py`<br>`User/unit/test_user_model.py` | `User/behavioral/test_auth_endpoints.py` | bcrypt, JWT, ORM model |

---

## Manual Testing Scripts

These scripts require Docker running with valid SMTP credentials in `.env`.

| Script | Purpose |
|--------|---------|
| `Alerts/run_alert_test.ps1` | Create alerts, trigger them, verify email |
| `Alerts/manual_alert_test.py` | Direct Python alert test harness |
| `Email/run_email_test.ps1` | Send test alert/reset emails via SMTP |
| `Email/manual_email_test.py` | Direct Python email test harness |

```powershell
# Example: verify SMTP is working
.\Testing\Email\run_email_test.ps1 -Action verify-smtp

# Example: trigger a price alert
.\Testing\Alerts\run_alert_test.ps1 -Action setup -Email you@example.com -Ticker AAPL -TargetPrice 200 -Direction above
```

---

## Why Some Tests Are Docker-Only

Some local versions of Pydantic are incompatible with the version of FastAPI used by the backend. All tests that import fastapi (behavioral tests, any test touching app.api.*) must run inside the Docker container, which uses a compatible Python + Pydantic v2 environment.

Unit tests avoid this by:
- Using only bcrypt, PyJWT, sqlalchemy, pandas, unittest.mock
- Inlining pure functions rather than importing from app.api.*
