# StockSense

StockSense is an AI-powered stock sentiment and portfolio platform. It combines market news sentiment with stock price data so users can track portfolios, monitor alerts, and understand how sentiment relates to returns.

Live frontend: https://ai-roosters-webpage.vercel.app/

Deployment and operations guide: [DEPLOYMENT.md](./DEPLOYMENT.md)

## Feature Overview
- News/Stock coverage note:
  - Due to API limits and capstone budget constraints, recent articles are gathered from four free APIs and we current look at 40 stocks.
  - Because of source rate-limiting, article counts per stock are also intentionally limited.
  - Sentiments may be impacted due to this limitation

- Secure authentication and account recovery:
  - Signup/login with JWT-based sessions.
  - Forgot-password and reset-password flow.
  - Profile management (name, username, phone, profile picture).
  - Daily login streak tracking.

- Personalized home experience:
  - At-a-glance portfolio summary.
  - Active alert preview.
  - Investor personality quiz.
  - "What If I Invested?" calculator for historical scenario analysis.
  - Rotating finance facts and streak widget.

- Interactive stocks dashboard:
  - Live ticker cards for supported stocks.
  - Watchlist starring with quick filtering. (Click the start to activate)
  - Positive/negative performance filters and sorting.
  - One-click add-to-portfolio actions.
  - Article sentiment summary context.

- Stock detail page:
  - Interactive price history chart with multiple time windows.
  - Return metrics across 1D/30D/120D/360D horizons.
  - Sentiment indicators and AI-generated news summary context.
  - Direct add-to-portfolio workflow from the stock page.

- Portfolio management and analytics:
  - Add, edit, remove, buy, and sell positions.
  - Unrealized and realized gain/loss tracking.
  - Transaction history and realized summary reporting.
  - Multi-stock side-by-side comparison with charting.
  - CSV and PDF export.
  - Portfolio import modal for faster onboarding.

- Alerts and monitoring:
  - Price-above and price-below alert creation.
  - Active and triggered alert history views.
  - Email delivery controlled by per-alert settings and the user-level `Market Alerts` preference.

- Net worth tracking:
  - Combined financial view across portfolio, assets, and liabilities.
  - Category-based allocation visualization.
  - Historical net worth snapshots and trend charts.
  - CSV and PDF export.

- News, sentiment, and AI pipelines:
  - Multi-source article ingestion, sentiment scoring, and aggregation pipelines.
  - FinBERT-based sentiment processing and stock-level rollups.
  - GPT-powered summary generation for stock news context.
  - Operationally scheduled via Azure Container Apps Jobs.


## Data Policy (Current)

- `stocks` stores full historical price data when full backfill is run.
- Return calculations are clamped to `2020-01-01` onward.
- Sentiment/AI snapshot pipeline uses 2020+ data only.
- API responses keep full price history but return fields are `null` for pre-2020 dates.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React + TypeScript + Vite |
| Backend | FastAPI + SQLAlchemy |
| Database | PostgreSQL (Neon in cloud) |
| Price data | yfinance |
| Sentiment | FinBERT (transformers) |
| Prediction | XGBoost |
| LLM summaries | OpenAI API |
| Deployment | Vercel (frontend), Azure Container Apps (backend/jobs), GHCR (images) |

## Supported Tickers

`KSS, ALK, NVS, AXP, FCX, CSX, DAL, NTAP, MRK, COP, BHP, EA, TSLA, NVDA, AAPL, MSFT, AMZN, AMD, META, GOOGL, GOOG, PLTR, MU, NFLX, NKE, AAL, BAC, F, INTC, XOM, T, SOFI, PLUG, MARA, SNAP, COIN, AMC, RIVN, CCL, ENPH`

## Quick Start (Local)

### 1. Configure environment

```bash
cp .env.example .env
```

Fill required values in `.env` (at minimum `DATABASE_URL`, `SECRET_KEY`, and any API keys you need for features).

### 2. Start app stack

```bash
docker compose up --build
```

This brings up:
- `postgres` on local port `5432`
- `api` on `http://localhost:8000`
- `frontend` on `http://localhost:5173`

### 3. Common manual commands

```powershell
# run only API + DB
docker compose up --build postgres api

# run backend API tests
.\Testing\run_all_tests.cmd -Suite backend

# run all default tests
.\Testing\run_all_tests.cmd

# run only stocks behavior tests
docker compose exec api python -m pytest /app/Testing/Stocks/behavior/test_stocks_api.py -v -ra
```

### 4. Manual pipeline commands (from repo root)

```bash
# price ingest
docker compose --profile pipeline run --rm pipeline python -m app.services.ingesting_pipelines.prices_ingest

# daily news ingest
docker compose --profile pipeline run --rm pipeline python -m app.services.ingesting_pipelines.daily_news_ingest

# historical HF news ingest
docker compose --profile pipeline run --rm pipeline python -m app.services.ingesting_pipelines.news_ingest

# FinBERT scoring
docker compose --profile pipeline run --rm pipeline python -m app.services.sentiment.article_processing

# returns recompute
docker compose --profile pipeline run --rm pipeline python -m app.services.sentiment.stock_processing

# sentiment aggregation + predictions
docker compose --profile pipeline run --rm pipeline python -m app.services.sentiment.aggregator
```

## Testing

All tests live under the `Testing/` directory.

Unit test files match the pattern: `Testing/*/unit/test_*.py` and `Testing/Alerts/test_*_unit.py`

Behavioral test files match the pattern: `Testing/*/behavioral/test_*.py` and `Testing/Stocks/behavior/test_*.py`

Sentiment BDD tests use Behave and live in: `Testing/Sentiment/behavioral/`

### Run all tests (recommended, requires Docker)

```powershell
.\Testing\run_all_tests.cmd
```

### Run only unit tests (no Docker required)

```powershell
.\Testing\run_all_tests.cmd -Suite unit -Mode local
```

### Run only behavioral tests (requires Docker running)

```powershell
.\Testing\run_all_tests.cmd -Suite behavioral
```

### Run unit tests manually (from repo root, no Docker)

```bash
cd backend
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

### Run behavioral tests manually (requires Docker running)

```bash
docker compose up -d
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

### Run sentiment BDD tests (requires Docker running)

```bash
docker compose exec api python -m behave /app/Testing/Sentiment/behavioral
```

### Run a single test file

```bash
# unit (local, from backend/)
python -m pytest ../Testing/Stocks/unit/test_price_ingest.py -v

# behavioral (Docker)
docker compose exec api python -m pytest ./Testing/Stocks/behavior/test_stocks_api.py -v
```

## Scheduler/Startup Behavior (Important)

- API startup jobs are controlled by:
  - `RUN_ARTICLE_INGEST`
  - `RUN_PRICE_INGEST`
  - `RUN_ML_PIPELINES`
- Local `docker-compose.yml` keeps article ingest off in API by default.
- Full-history startup price backfill is opt-in with:
  - `INGEST_ALL_YEARS=1`
- Default startup price mode is incremental:
  - `INGEST_ALL_YEARS=0`
  - `PRICE_INGEST_LOOKBACK_DAYS=30`

## Repository Structure

```text
ai_roosters/
  backend/
    app/
      api/
      core/
      db/
      jobs/
      models/
      schema/
      services/
        ingesting_pipelines/
        sentiment/
  frontend/
    src/
  Testing/
  docker-compose.yml
  README.md
  DEPLOYMENT.md
```

## Team

- Katie Jones
- Connor Thiele
- Sofia Bacha
- Kevin Do
- Andrew Lim
