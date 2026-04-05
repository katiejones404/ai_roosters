# StockSense

StockSense is an AI-powered stock sentiment and portfolio platform. It combines market news sentiment with stock price data so users can track portfolios, monitor alerts, and understand how sentiment relates to returns.

Live frontend: https://ai-roosters-webpage.vercel.app/

Deployment and operations guide: [DEPLOYMENT.md](./DEPLOYMENT.md)

## What The App Does

- Auth and profiles: signup, login, JWT sessions, profile editing, profile picture upload.
- Portfolio tracking: holdings, gain/loss, return metrics, comparisons, CSV/PDF export.
- Net worth tracking: assets/liabilities, history charts, CSV/PDF export.
- Stocks dashboard: live prices, return metrics, sentiment context.
- Alerts: price-above/price-below triggers with optional email notifications.
- News and sentiment: article ingest + FinBERT scoring + aggregated snapshots + GPT explanations.

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

```bash
# run only API + DB
docker compose up --build postgres api

# run API tests (PowerShell helper)
./run_testing.ps1

# run all tests (Python runner)
python run_testing.py

# run only stocks behavior tests
python -m pytest Testing/Stocks/behavior/test_stocks_api.py -v
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

- Connor Thiele
- Katie Jones
- Sofia Bacha
- Kevin Do
- Andrew Lim
