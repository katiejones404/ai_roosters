# StockSense - AI-Powered Stock Sentiment Dashboard

Live website: https://ai-roosters-webpage.vercel.app/

Backend API health: 

---

## About StockSense

StockSense is a full-stack web application that helps investors understand how financial news sentiment relates to stock performance. Users can build a personal portfolio, track real price data and historical returns, and read AI-generated summaries explaining what market sentiment means for each stock.

The core question the project addresses: **does the tone of financial news predict short, medium, and long-term stock returns?** StockSense answers this visually and in plain language using a machine learning pipeline built on FinBERT, XGBoost, and GPT-4o-mini.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + TypeScript, Recharts, Vite |
| Backend | FastAPI (Python) |
| Database | PostgreSQL via Neon (serverless, cloud) |
| Sentiment | FinBERT (HuggingFace transformers) |
| Prediction | XGBoost regression |
| Summaries | GPT-4o-mini (OpenAI) |
| Auth | JWT (JSON Web Tokens) |
| Deployment | Frontend on Vercel, Backend on Azure Container Apps |

---

## Features

### Authentication and User Management
- JWT-based authentication: register, login, logout, and persistent sessions
- Secure password hashing
- Profile picture upload stored as base64
- User profile editing: name, phone, username
- Account deletion with password confirmation

### Portfolio
- Add any supported ticker with quantity and average purchase price
- Real-time display of: current price, cost basis, total gain/loss, 1D/30D/120D/360D returns
- Animated count-up for all summary stat cards
- Per-holding gain/loss bar chart (green/red by position)
- Portfolio comparison mode: select 2 or more holdings to compare with an area chart and side-by-side metrics table
- Export portfolio to CSV or PDF

### Net Worth Tracker
- Track manual assets (cash, savings, real estate, vehicle, other) and liabilities
- Summary cards: net worth, portfolio value, total assets, total liabilities
- Net worth history line chart (30D/90D/1Y range)
- Asset distribution donut chart
- Export net worth to CSV or PDF

### Dashboard and Stock Discovery
- Card-based dashboard showing all 40 supported tickers with sentiment indicators
- Each card shows: current price, 1D/30D/120D/360D return metrics, and FinBERT sentiment label
- Live search by ticker or company name
- Trending widget showing top portfolio performers by 1D return

### Market News
- Latest financial news articles from tracked stocks
- Filter by ticker
- Load-more pagination
- Linked directly to source articles

### Price Alerts
- Set price alerts: trigger above or below a target price
- Notification bell in navbar
- Email notification on trigger (SMTP-based)

### Sentiment Analysis
- FinBERT sentiment scores (positive/neutral/negative) per article
- Sentiment snapshots aggregated per (ticker, date)
- XGBoost-predicted returns shown alongside realized returns
- GPT-4o-mini explanations of sentiment context per ticker

---

## Supported Tickers (40 total)

| Group | Tickers |
|---|---|
| Original | KSS, ALK, NVS, AXP, FCX, CSX, DAL, NTAP, MRK, COP, BHP, EA |
| Large Cap Tech | TSLA, NVDA, AAPL, MSFT, AMZN, AMD, META, GOOGL, GOOG, PLTR, MU, NFLX |
| Diversified | NKE, AAL, BAC, F, INTC, XOM, T |
| High Volatility | SOFI, PLUG, MARA, SNAP, COIN, AMC, RIVN, CCL, ENPH |

---

## Data Pipeline

Steps are run via Docker Compose pipeline profile:

```
1. Historical news ingest    -> articles table (HuggingFace, 2020-2023)
2. Daily news ingest         -> stock_news_articles table (Marketaux API)
3. NewsAPI ingest            -> stock_news_articles table
4. AlphaVantage ingest       -> stock_news_articles table
5. Guardian ingest           -> stock_news_articles table
6. Price ingest              -> stocks table (yfinance)
7. FinBERT scoring           -> scores all unscored articles
8. Returns pipeline          -> computes 1D/30D/120D/360D forward returns
9. Sentiment aggregator      -> sentiment_snapshots table
10. GPT summaries            -> one explanation per ticker
```

### Key Database Tables

| Table | Rows | Description |
|---|---|---|
| articles | ~63,000 | Historical news (HuggingFace) |
| stock_news_articles | varies | Daily news (Marketaux, NewsAPI, AlphaVantage, Guardian) |
| stocks | ~23,000+ | Price data (yfinance) |
| sentiment_snapshots | ~23,000+ | Aggregated sentiment and returns per ticker/date |

---

## Deployment

### Backend (Azure Container Apps)

```powershell
az containerapp create --name stocksense-api --resource-group stocksense-rg --environment stocksense-env --image "ghcr.io/katiejones404/stocksense-api:latest" --registry-server "ghcr.io" --registry-username katiejones404 --registry-password $GH_PAT --target-port 8000 --ingress external --min-replicas 1 --cpu 1.0 --memory 2.0Gi
```

### Production Scheduling (Azure Container Apps Jobs)

For production, run recurring work as Container Apps Jobs (not in-process API loops).

1. Disable API in-process schedulers:

```powershell
az containerapp update `
  --name stocksense-api `
  --resource-group stocksense-rg `
  --set-env-vars ENABLE_BACKGROUND_SCHEDULERS=0 RUN_ARTICLE_INGEST=0 RUN_PRICE_INGEST=0 RUN_ML_PIPELINES=0
```

2. Create scheduled jobs (cron is UTC):

```powershell
# Alerts every 5 minutes
az containerapp job create `
  --name stocksense-alerts-job `
  --resource-group stocksense-rg `
  --environment stocksense-env `
  --trigger-type Schedule `
  --cron-expression "*/5 * * * *" `
  --image ghcr.io/katiejones404/stocksense-api:latest `
  --registry-server ghcr.io `
  --registry-username katiejones404 `
  --registry-password $GH_PAT `
  --cpu 0.5 --memory 1.0Gi `
  --replica-timeout 900 --replica-retry-limit 1 `
  --command python `
  --args -m app.jobs.run_alert_checks_once `
  --secrets database-url="$DATABASE_URL" smtp-user="$SMTP_USER" smtp-pass="$SMTP_PASS" alert-from="$ALERT_FROM_EMAIL" `
  --env-vars DATABASE_URL=secretref:database-url SMTP_USER=secretref:smtp-user SMTP_PASS=secretref:smtp-pass ALERT_FROM_EMAIL=secretref:alert-from SMTP_HOST=smtp.gmail.com SMTP_PORT=587

# Price ingest every 15 minutes during market hours (job itself runs all day; ingestion module handles data window)
az containerapp job create `
  --name stocksense-prices-job `
  --resource-group stocksense-rg `
  --environment stocksense-env `
  --trigger-type Schedule `
  --cron-expression "*/15 * * * 1-5" `
  --image ghcr.io/katiejones404/stocksense-api:latest `
  --registry-server ghcr.io `
  --registry-username katiejones404 `
  --registry-password $GH_PAT `
  --cpu 0.5 --memory 1.0Gi `
  --replica-timeout 1800 --replica-retry-limit 1 `
  --command python `
  --args -m app.services.ingesting_pipelines.prices_ingest `
  --secrets database-url="$DATABASE_URL" `
  --env-vars DATABASE_URL=secretref:database-url PRICE_UPDATE_EXISTING=1

# News ingest every 2 hours
az containerapp job create `
  --name stocksense-news-job `
  --resource-group stocksense-rg `
  --environment stocksense-env `
  --trigger-type Schedule `
  --cron-expression "5 */2 * * *" `
  --image ghcr.io/katiejones404/stocksense-api:latest `
  --registry-server ghcr.io `
  --registry-username katiejones404 `
  --registry-password $GH_PAT `
  --cpu 0.5 --memory 1.0Gi `
  --replica-timeout 1800 --replica-retry-limit 1 `
  --command python `
  --args -m app.services.ingesting_pipelines.daily_news_ingest `
  --secrets database-url="$DATABASE_URL" marketaux-token="$MARKETAUX_API_TOKEN" `
  --env-vars DATABASE_URL=secretref:database-url MARKETAUX_API_TOKEN=secretref:marketaux-token

# Sentiment refresh every 6 hours (pipeline image with ML deps)
az containerapp job create `
  --name stocksense-sentiment-job `
  --resource-group stocksense-rg `
  --environment stocksense-env `
  --trigger-type Schedule `
  --cron-expression "25 */6 * * *" `
  --image ghcr.io/katiejones404/stocksense-pipeline:latest `
  --registry-server ghcr.io `
  --registry-username katiejones404 `
  --registry-password $GH_PAT `
  --cpu 1.0 --memory 2.0Gi `
  --replica-timeout 3600 --replica-retry-limit 1 `
  --command sh `
  --args -c "python -m app.services.sentiment.article_processing && python -m app.services.sentiment.stock_processing && python -m app.services.sentiment.aggregator" `
  --secrets database-url="$DATABASE_URL" openai-key="$OPENAI_API_KEY" `
  --env-vars DATABASE_URL=secretref:database-url OPENAI_API_KEY=secretref:openai-key
```

3. Validate and run on demand:

```powershell
az containerapp job execution list --name stocksense-news-job --resource-group stocksense-rg -o table
az containerapp job start --name stocksense-news-job --resource-group stocksense-rg
```

### Build Pipeline Image In GitHub Actions (No Local Heavy Build)

Workflow file:
- `.github/workflows/build-pipeline-image.yml`

What it does:
- Builds `backend/Pipeline.Dockerfile` on GitHub-hosted runners.
- Pushes to `ghcr.io/<repo-owner-lowercase>/stocksense-pipeline`.
- Publishes tags:
  - `latest` (default branch only)
  - `sha-<commit>`

How to run:
1. Push to `main` (when pipeline-related files changed), or
2. In GitHub: **Actions -> Build And Push Pipeline Image -> Run workflow**

After it succeeds, use this image in Azure jobs:
- `ghcr.io/<repo-owner-lowercase>/stocksense-pipeline:latest`

### Frontend (Vercel)

Deployed automatically from GitHub. Set environment variable:
- `VITE_API_BASE_URL` = Azure Container App URL

### Database (Neon PostgreSQL)

Cloud-hosted serverless PostgreSQL. Connection via `DATABASE_URL` environment variable.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| DATABASE_URL | Yes | Neon PostgreSQL connection string |
| OPENAI_API_KEY | Yes | GPT-4o-mini summaries |
| MARKETAUX_API_TOKEN | For pipeline | Daily news ingest |
| NEWSAPI_API_KEY | For pipeline | NewsAPI ingest |
| ALPHAVANTAGE_API_KEY | For pipeline | AlphaVantage ingest |
| GUARDIAN_API_KEY | For pipeline | Guardian ingest |
| SECRET_KEY | Yes | JWT signing key |
| FRONTEND_ORIGINS | Yes | CORS allowed origins |
| RUN_ARTICLE_INGEST | Optional | Set to 1 to run historical article ingest on API startup (default 0) |
| RUN_PRICE_INGEST | Optional | Set to 1 to run price ingest on startup |
| RUN_ML_PIPELINES | Optional | Set to 1 to run FinBERT/XGBoost on startup |
| ENABLE_BACKGROUND_SCHEDULERS | Optional | Set to 0 to disable in-process API loops (recommended when using ACA Jobs) |
| ENABLE_ALERT_SCHEDULER | Optional | Enable/disable in-process alert loop |
| ENABLE_PRICE_INGEST_SCHEDULER | Optional | Enable/disable in-process price loop |
| ENABLE_NEWS_INGEST_SCHEDULER | Optional | Enable/disable in-process news loop |
| ENABLE_SENTIMENT_SCHEDULER | Optional | Enable/disable in-process sentiment loop |
| NEWS_INGEST_FILTERED_MODE | Optional | `1` uses filtered HF subsets (Colab-style) instead of full-dataset scan |
| NEWS_INGEST_HF_SUBSETS | Optional | Comma-separated HF subset names for historical news ingest |
| SMTP_HOST | For alerts | Email alert SMTP server |
| SMTP_USER | For alerts | Email alert sender address |
| SMTP_PASS | For alerts | Email alert password |

---

## Running Locally

```bash
# 1. Clone the repo and set up .env
cp .env.example .env
# fill in required values

# 2. Start services
docker compose up

# 3. (Optional) Run the data pipeline

docker compose --profile pipeline run --rm pipeline python -m app.services.ingesting_pipelines.prices_ingest
docker compose --profile pipeline run --rm pipeline python -m app.services.ingesting_pipelines.daily_news_ingest
docker compose --profile pipeline run --rm pipeline python -m app.services.sentiment.article_processing
docker compose --profile pipeline run --rm pipeline python -m app.services.sentiment.aggregator
```

---

## Project Structure

```
ai_roosters/
  backend/
    app/
      api/           # FastAPI route handlers
      models/        # SQLAlchemy models
      schema/        # Pydantic schemas
      services/
        ingesting_pipelines/   # News and price ingest scripts
        sentiment/             # FinBERT, returns, aggregator, GPT
      db/            # Database connection
  frontend/
    src/
      components/    # Navbar, LoadingScreen, AddToPortfolio, StockChartBg
      utils/         # Auth, sentiment helpers, stock name mapping
      *.tsx          # Page components
  notebooks/         # Google Colab notebooks for Neon ingest
  docker-compose.yml
  README.md
```
---
## Authors

Connor Thiele — cthiele@email.sc.edu

Katie Jones — Katie.jones4@outlook.com

Sofia Bacha — sofbacha01@gmail.com

Kevin Do — kdox1023@gmail.com

Andrew Lim — andrew.lim0023@gmail.com

