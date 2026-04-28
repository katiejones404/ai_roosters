# Deployment Guide

This file contains deployment, operations, and manual run commands for StockSense.

## Production Architecture

- Frontend: Vercel
- Backend API: Azure Container Apps (`stocksense-api`)
- Database: Neon PostgreSQL (`DATABASE_URL`)
- Container registry: GitHub Container Registry (GHCR)
- Scheduled workloads: Azure Container Apps Jobs

## GitHub Workflows (Current)

### API image workflow

File: `.github/workflows/build-api-image.yml`

- Builds and pushes: `ghcr.io/<owner>/stocksense-api`
- Triggered on `main` pushes that touch:
  - `backend/API.Dockerfile`
  - `backend/requirements-api.txt`
  - `backend/app/**`
  - `.github/workflows/build-api-image.yml`
- Workflow builds/pushes image to GHCR.
- Azure deploy is run manually via `azuredeployment/deploy_update.sh`.

### Pipeline image workflow

File: `.github/workflows/build-pipeline-image.yml`

- Builds and pushes: `ghcr.io/<owner>/stocksense-pipeline`
- Triggered on `main` pushes that touch:
  - `backend/Pipeline.Dockerfile`
  - `backend/requirements-pipeline.txt`
  - `backend/requirements-api.txt`
  - `backend/app/services/sentiment/**`
  - `backend/app/services/ingesting_pipelines/**`
  - `.github/workflows/build-pipeline-image.yml`
- Workflow builds/pushes image to GHCR.

### University Tenant Note (No Service Principal Access)

If your tenant blocks service principal creation, skip GitHub-to-Azure auth (`AZURE_CREDENTIALS`) and deploy manually:

USC is the tenant for our Azure accounts and blocks automatic deployment.

```bash
cd azuredeployment
source .deploy.env
bash deploy_update.sh
```

## Azure Setup

### 1. Create API Container App (one-time)

```powershell
az containerapp create --name stocksense-api --resource-group stocksense-rg --environment stocksense-env --image "ghcr.io/<owner>/stocksense-api:latest" --registry-server "ghcr.io" --registry-username <gh-user> --registry-password $GH_PAT --target-port 8000 --ingress external --min-replicas 1 --cpu 1.0 --memory 2.0Gi
```

### 2. Recommended API env settings for production

Disable in-process schedulers and one-time startup jobs when using ACA Jobs:

```powershell
az containerapp update `
  --name stocksense-api `
  --resource-group stocksense-rg `
  --set-env-vars ENABLE_BACKGROUND_SCHEDULERS=0 RUN_ARTICLE_INGEST=0 RUN_PRICE_INGEST=0 RUN_ML_PIPELINES=0
```

### 3. Startup price ingest mode controls

If you do run `RUN_PRICE_INGEST=1`, choose mode with:

- `INGEST_ALL_YEARS=0` (default): incremental startup ingest only
- `INGEST_ALL_YEARS=1`: full-history startup backfill (`period=max`)
- `PRICE_INGEST_LOOKBACK_DAYS=30`: incremental lookback window

Example:

```powershell
az containerapp update `
  --name stocksense-api `
  --resource-group stocksense-rg `
  --set-env-vars RUN_PRICE_INGEST=1 INGEST_ALL_YEARS=0 PRICE_INGEST_LOOKBACK_DAYS=30
```

## Azure Container Apps Jobs (Recommended)

### Job Purpose + Schedule (Current)

- `stocksense-prices` (`*/15 * * * *`): pulls latest market prices into your DB every 15 minutes.
- `stocksense-news-ingest` (`0 12,20 * * *`): ingests news from your configured news sources twice daily.
- `stocksense-sentiment-summary` (`30 13,21 * * *`): runs article sentiment, stock sentiment aggregation, and GPT summary after news ingest.
- `stocksense-alerts` (`*/5 * * * *`): runs alert checks and email delivery every 5 minutes (only if this job exists in your environment).

### About `stocksense-sentiment`

`stocksense-sentiment` is a legacy/extra sentiment job from an older setup. It is not created by the current `setup_azure_once.sh` script.

- If it runs similar sentiment modules, it can duplicate work done by `stocksense-sentiment-summary`.
- Recommended: keep only one sentiment pipeline job unless you intentionally want both.

To check exact live cron values:

```bash
az containerapp job show --name stocksense-prices --resource-group "$RG" --query properties.configuration.scheduleTriggerConfig.cronExpression -o tsv
az containerapp job show --name stocksense-news-ingest --resource-group "$RG" --query properties.configuration.scheduleTriggerConfig.cronExpression -o tsv
az containerapp job show --name stocksense-sentiment --resource-group "$RG" --query properties.configuration.scheduleTriggerConfig.cronExpression -o tsv
az containerapp job show --name stocksense-sentiment-summary --resource-group "$RG" --query properties.configuration.scheduleTriggerConfig.cronExpression -o tsv
az containerapp job show --name stocksense-alerts --resource-group "$RG" --query properties.configuration.scheduleTriggerConfig.cronExpression -o tsv
```

### Alerts job (every 5 minutes)

```powershell
az containerapp job create `
  --name stocksense-alerts-job `
  --resource-group stocksense-rg `
  --environment stocksense-env `
  --trigger-type Schedule `
  --cron-expression "*/5 * * * *" `
  --image ghcr.io/<owner>/stocksense-api:latest `
  --registry-server ghcr.io `
  --registry-username <gh-user> `
  --registry-password $GH_PAT `
  --cpu 0.5 --memory 1.0Gi `
  --replica-timeout 900 --replica-retry-limit 1 `
  --command sh `
  --args "-c" "python -m app.jobs.run_alert_checks_once" `
  --secrets database-url="$DATABASE_URL" smtp-user="$SMTP_USER" smtp-pass="$SMTP_PASS" alert-from="$ALERT_FROM_EMAIL" `
  --env-vars DATABASE_URL=secretref:database-url SMTP_USER=secretref:smtp-user SMTP_PASS=secretref:smtp-pass ALERT_FROM_EMAIL=secretref:alert-from SMTP_HOST=smtp.gmail.com SMTP_PORT=587
```

### Price ingest job (weekdays every 15 minutes)

```powershell
az containerapp job create `
  --name stocksense-prices-job `
  --resource-group stocksense-rg `
  --environment stocksense-env `
  --trigger-type Schedule `
  --cron-expression "*/15 * * * 1-5" `
  --image ghcr.io/<owner>/stocksense-api:latest `
  --registry-server ghcr.io `
  --registry-username <gh-user> `
  --registry-password $GH_PAT `
  --cpu 0.5 --memory 1.0Gi `
  --replica-timeout 1800 --replica-retry-limit 1 `
  --command sh `
  --args "-c" "python -m app.services.ingesting_pipelines.prices_ingest" `
  --secrets database-url="$DATABASE_URL" `
  --env-vars DATABASE_URL=secretref:database-url PRICE_UPDATE_EXISTING=1
```

### News ingest job (twice/day, all 4 sources)

```powershell
az containerapp job create `
  --name stocksense-news-job `
  --resource-group stocksense-rg `
  --environment stocksense-env `
  --trigger-type Schedule `
  --cron-expression "0 12,20 * * *" `
  --image ghcr.io/<owner>/stocksense-api:latest `
  --registry-server ghcr.io `
  --registry-username <gh-user> `
  --registry-password $GH_PAT `
  --cpu 0.5 --memory 1.0Gi `
  --replica-timeout 3600 --replica-retry-limit 1 `
  --command sh `
  --args "-c" "python -m app.jobs.run_news_ingest_once" `
  --secrets database-url="$DATABASE_URL" marketaux-token="$MARKETAUX_API_TOKEN" newsapi-key="$NEWSAPI_API_KEY" alphavantage-key="$ALPHAVANTAGE_API_KEY" guardian-key="$GUARDIAN_API_KEY" `
  --env-vars DATABASE_URL=secretref:database-url MARKETAUX_API_TOKEN=secretref:marketaux-token NEWSAPI_API_KEY=secretref:newsapi-key ALPHAVANTAGE_API_KEY=secretref:alphavantage-key GUARDIAN_API_KEY=secretref:guardian-key NEWS_LOOKBACK_HOURS=24 NEWS_MAX_PAGES_PER_TICKER=1 NEWS_API_LIMIT_PER_PAGE=2 NEWS_MAX_ARTICLES_PER_TICKER=2 NEWSAPI_LOOKBACK_DAYS=1 NEWSAPI_MAX_PAGES=1 NEWSAPI_PAGE_SIZE=2 ALPHAVANTAGE_LOOKBACK_DAYS=1 ALPHAVANTAGE_LIMIT=2 ALPHAVANTAGE_DELAY_SECS=13 GUARDIAN_LOOKBACK_DAYS=1 GUARDIAN_MAX_PAGES=1 GUARDIAN_PAGE_SIZE=2
```

This uses `app.jobs.run_news_ingest_once`, which runs Marketaux + NewsAPI + AlphaVantage + Guardian in sequence and skips sources whose API keys are missing.

Current deployment script creates the job with:

```bash
python app/jobs/run_news_ingest_once.py
```

### Sentiment job (every 6 hours, pipeline image)

```powershell
az containerapp job create `
  --name stocksense-sentiment-job `
  --resource-group stocksense-rg `
  --environment stocksense-env `
  --trigger-type Schedule `
  --cron-expression "25 */6 * * *" `
  --image ghcr.io/<owner>/stocksense-pipeline:latest `
  --registry-server ghcr.io `
  --registry-username <gh-user> `
  --registry-password $GH_PAT `
  --cpu 1.0 --memory 2.0Gi `
  --replica-timeout 3600 --replica-retry-limit 1 `
  --command sh `
  --args "-c" "python -m app.services.sentiment.article_processing && python -m app.services.sentiment.stock_processing && python -m app.services.sentiment.aggregator" `
  --secrets database-url="$DATABASE_URL" openai-key="$OPENAI_API_KEY" `
  --env-vars DATABASE_URL=secretref:database-url OPENAI_API_KEY=secretref:openai-key
```

Current deployment script creates `stocksense-sentiment-summary` with:

```bash
python app/jobs/run_sentiment_summary_once.py
```

This wrapper runs, in order:
1. `app.services.sentiment.article_processing`
2. `app.services.sentiment.stock_processing` (returns pipeline)
3. `app.services.sentiment.aggregator`
4. `app.services.sentiment.gpt_summary`

## Manual Azure Operations

```powershell
# list latest executions
az containerapp job execution list --name stocksense-news-job --resource-group stocksense-rg -o table

# start a job immediately
az containerapp job start --name stocksense-news-job --resource-group stocksense-rg

# update API to a specific image tag
az containerapp update --name stocksense-api --resource-group stocksense-rg --image ghcr.io/<owner>/stocksense-api:latest
```

## Manual Local Operations

### Run app locally

```bash
docker compose up --build
```

### Run only API and DB

```bash
docker compose up --build postgres api
```

### Run pipeline steps manually

```bash
docker compose --profile pipeline run --rm pipeline python -m app.services.ingesting_pipelines.prices_ingest
docker compose --profile pipeline run --rm pipeline python -m app.services.ingesting_pipelines.daily_news_ingest
docker compose --profile pipeline run --rm pipeline python -m app.services.ingesting_pipelines.news_ingest
docker compose --profile pipeline run --rm pipeline python -m app.services.sentiment.article_processing
docker compose --profile pipeline run --rm pipeline python -m app.services.sentiment.stock_processing
docker compose --profile pipeline run --rm pipeline python -m app.services.sentiment.aggregator
```

### One-time full-history price ingest locally

```bash
# in .env set:
# RUN_PRICE_INGEST=1
# INGEST_ALL_YEARS=1
# RUN_ARTICLE_INGEST=0
# RUN_ML_PIPELINES=0

docker compose up --build api
```

Then set `INGEST_ALL_YEARS=0` again for normal incremental startup behavior.

### Backfill Neon with pre-2020 prices (recommended one-time command to get pre-2020 stock data)

`What If` does not depend on the `stocks` table; it calls Yahoo data through `/api/stock-history` directly.
Backfilling Neon is still useful for portfolio/history use cases.

```bash
# Ensure .env DATABASE_URL points to Neon first.
docker compose --profile pipeline run --rm \
  -e PRICE_PERIOD=max \
  -e PRICE_UPDATE_EXISTING=1 \
  pipeline python -m app.services.ingesting_pipelines.prices_ingest
```

Recompute returns after backfill (returns remain null before 2020 by policy):

```bash
docker compose --profile pipeline run --rm \
  -e RETURNS_ONLY_MISSING=1 \
  pipeline python -m app.services.sentiment.stock_processing
```

## Environment Variables You Should Know

Core:
- `DATABASE_URL`
- `SECRET_KEY`
- `FRONTEND_ORIGINS`
- `FRONTEND_URL`

Startup controls:
- `RUN_ARTICLE_INGEST`
- `RUN_PRICE_INGEST`
- `RUN_ML_PIPELINES`
- `INGEST_ALL_YEARS`
- `PRICE_INGEST_LOOKBACK_DAYS`

Scheduler controls:
- `ENABLE_BACKGROUND_SCHEDULERS`
- `ENABLE_ALERT_SCHEDULER`
- `ENABLE_PRICE_INGEST_SCHEDULER`
- `ENABLE_NEWS_INGEST_SCHEDULER`
- `ENABLE_SENTIMENT_SCHEDULER`

Pipeline tuning:
- `RETURNS_ONLY_MISSING`
- `RETURNS_BATCH_SIZE`
- `RETURNS_START_DATE` (default cutoff behavior is 2020-01-01)
- `AGG_START_DATE`
- `AGG_END_DATE`

News limits:
- `NEWS_MAX_PAGES_PER_TICKER`
- `NEWS_API_LIMIT_PER_PAGE`
- `NEWS_MAX_ARTICLES_PER_TICKER`
- `NEWS_LOOKBACK_HOURS`
