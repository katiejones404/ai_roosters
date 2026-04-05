# StockSense Deployment on Azure 

This guide shows exactly what to run:

- one-time Azure setup
- recurring deploy steps after code updates
- health checks and troubleshooting checks

## 0) Prerequisites

Install and verify:

```bash
az version
git --version
```

Optional but useful:

```bash
gh --version
```

## 1) Create your deployment env file (once)

In repo root, create `.deploy.env` with your real values:

```bash
cat > .deploy.env <<'EOF'
SUBSCRIPTION_ID="<your-azure-subscription-id>"
RG="stocksense-rg"
ENV_NAME="stocksense-env"
API_APP="stocksense-api"

GH_USER="katiejones404"
GH_PAT="<your-ghcr-pat>"

API_IMAGE="ghcr.io/katiejones404/stocksense-api:latest"
PIPE_IMAGE="ghcr.io/katiejones404/stocksense-pipeline:latest"

DATABASE_URL="<your-neon-database-url>"
FRONTEND_ORIGINS="https://ai-roosters-webpage.vercel.app"

MARKETAUX_API_TOKEN="<marketaux-key>"
NEWSAPI_API_KEY="<newsapi-key>"
ALPHAVANTAGE_API_KEY="<alphavantage-key>"
GUARDIAN_API_KEY="<guardian-key>"
OPENAI_API_KEY="<openai-key>"

SMTP_USER="<smtp-user>"
SMTP_PASS="<smtp-pass>"
ALERT_FROM_EMAIL="<from-email>"
EOF
```

Load env vars each terminal session:

```bash
source .deploy.env
```

## 2) One-time infrastructure setup

Run:

```bash
bash setup_azure_once.sh
```

This script will:

- login check and set subscription
- create resource group + ACA environment if missing
- create/update API container app
- set API env vars
- create/recreate these jobs:
  - `stocksense-alerts`
  - `stocksense-prices`
  - `stocksense-news-ingest`
  - `stocksense-sentiment-summary`

## 3) Every time you update code

### 3.1 Push code to `main`

```bash
git add .
git commit -m "your update message"
git push origin main
```

### 3.2 Wait for GitHub Actions images to finish

Check in GitHub Actions UI, or with `gh`:

```bash
gh run list --limit 10
```

### 3.3 Deploy latest images to Azure

```bash
bash deploy_update.sh
```

This script updates:

- API container image to latest
- all jobs to latest image tags
- prints health/job checks

## 4) Manual checks (anytime)

### API health

```bash
API_FQDN=$(az containerapp show --name "$API_APP" --resource-group "$RG" --query properties.configuration.ingress.fqdn -o tsv)
echo "https://$API_FQDN"
curl "https://$API_FQDN/health"
```

### List jobs

```bash
az containerapp job list -g "$RG" -o table
```

### Check executions

```bash
az containerapp job execution list --name stocksense-prices --resource-group "$RG" -o table
az containerapp job execution list --name stocksense-news-ingest --resource-group "$RG" -o table
az containerapp job execution list --name stocksense-sentiment-summary --resource-group "$RG" -o table
```

### Force-run jobs now

```bash
az containerapp job start --name stocksense-prices --resource-group "$RG"
az containerapp job start --name stocksense-news-ingest --resource-group "$RG"
az containerapp job start --name stocksense-sentiment-summary --resource-group "$RG"
```

## 5) Important behavior notes

- API in-process schedulers are intentionally disabled in Azure (`ENABLE_BACKGROUND_SCHEDULERS=0`).
- Jobs are the source of truth for recurring ingestion and sentiment pipelines.
- Prices job is set to run every 15 minutes, every day.
- Returns are clamped to 2020+ by your backend policy.

## 6) Optional one-time Neon backfill for full price history

```bash
az containerapp job delete --name stocksense-price-backfill --resource-group "$RG" --yes >/dev/null 2>&1 || true

az containerapp job create \
  --name stocksense-price-backfill \
  --resource-group "$RG" \
  --environment "$ENV_NAME" \
  --image "$API_IMAGE" \
  --registry-server ghcr.io \
  --registry-username "$GH_USER" \
  --registry-password "$GH_PAT" \
  --trigger-type Manual \
  --parallelism 1 \
  --replica-completion-count 1 \
  --replica-retry-limit 1 \
  --replica-timeout 7200 \
  --command "sh,-c,python -m app.services.ingesting_pipelines.prices_ingest && python -m app.services.sentiment.stock_processing" \
  --secrets "database-url=$DATABASE_URL" \
  --env-vars \
    DATABASE_URL=secretref:database-url \
    PRICE_PERIOD=max \
    PRICE_UPDATE_EXISTING=1 \
    RETURNS_ONLY_MISSING=1

az containerapp job start --name stocksense-price-backfill --resource-group "$RG"
```
