#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$SCRIPT_DIR/.deploy.env"

if [[ ! -f "$ENV_FILE" && -f "$ROOT_DIR/.deploy.env" ]]; then
  ENV_FILE="$ROOT_DIR/.deploy.env"
fi

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
else
  echo "Missing .deploy.env. Expected at:"
  echo "  - $SCRIPT_DIR/.deploy.env (recommended)"
  echo "  - $ROOT_DIR/.deploy.env (fallback)"
  exit 1
fi

require_var() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required env var: $name"
    exit 1
  fi
}

for v in SUBSCRIPTION_ID RG ENV_NAME API_APP GH_USER GH_PAT API_IMAGE PIPE_IMAGE DATABASE_URL FRONTEND_ORIGINS OPENAI_API_KEY SMTP_USER SMTP_PASS ALERT_FROM_EMAIL MARKETAUX_API_TOKEN NEWSAPI_API_KEY ALPHAVANTAGE_API_KEY GUARDIAN_API_KEY; do
  require_var "$v"
done
FRONTEND_URL="${FRONTEND_URL:-$FRONTEND_ORIGINS}"
LOCATION="${LOCATION:-eastus2}"

echo "[1/7] Checking Azure login..."
az account show >/dev/null 2>&1 || az login >/dev/null
az account set --subscription "$SUBSCRIPTION_ID"

echo "[2/7] Ensuring resource group + ACA environment..."
az group create --name "$RG" --location "$LOCATION" >/dev/null

if ! az containerapp env show --name "$ENV_NAME" --resource-group "$RG" >/dev/null 2>&1; then
  az containerapp env create --name "$ENV_NAME" --resource-group "$RG" --location "$LOCATION" >/dev/null
fi

echo "[3/7] Creating/updating API app..."
if az containerapp show --name "$API_APP" --resource-group "$RG" >/dev/null 2>&1; then
  az containerapp update \
    --name "$API_APP" \
    --resource-group "$RG" \
    --image "$API_IMAGE" >/dev/null
else
  az containerapp create \
    --name "$API_APP" \
    --resource-group "$RG" \
    --environment "$ENV_NAME" \
    --image "$API_IMAGE" \
    --registry-server ghcr.io \
    --registry-username "$GH_USER" \
    --registry-password "$GH_PAT" \
    --target-port 8000 \
    --ingress external \
    --cpu 1.0 \
    --memory 2.0Gi \
    --min-replicas 1 >/dev/null
fi

# Keep registry credentials in a separate call for broader az CLI compatibility.
az containerapp registry set \
  --name "$API_APP" \
  --resource-group "$RG" \
  --server ghcr.io \
  --username "$GH_USER" \
  --password "$GH_PAT" >/dev/null

echo "[4/7] Setting API environment variables..."
az containerapp update \
  --name "$API_APP" \
  --resource-group "$RG" \
  --set-env-vars \
    DATABASE_URL="$DATABASE_URL" \
    FRONTEND_ORIGINS="$FRONTEND_ORIGINS" \
    FRONTEND_URL="$FRONTEND_URL" \
    ENABLE_BACKGROUND_SCHEDULERS=0 \
    RUN_ARTICLE_INGEST=0 \
    RUN_PRICE_INGEST=0 \
    RUN_ML_PIPELINES=0 \
    INGEST_ALL_YEARS=0 \
    PRICE_INGEST_LOOKBACK_DAYS=30 >/dev/null

recreate_job() {
  local name="$1"
  az containerapp job delete --name "$name" --resource-group "$RG" --yes >/dev/null 2>&1 || true
}

echo "[5/7] Recreating alerts job..."
recreate_job "stocksense-alerts"
az containerapp job create \
  --name stocksense-alerts \
  --resource-group "$RG" \
  --environment "$ENV_NAME" \
  --image "$API_IMAGE" \
  --registry-server ghcr.io \
  --registry-username "$GH_USER" \
  --registry-password "$GH_PAT" \
  --trigger-type Schedule \
  --cron-expression "*/5 * * * *" \
  --parallelism 1 \
  --replica-completion-count 1 \
  --replica-retry-limit 1 \
  --replica-timeout 900 \
  --command "python" \
  --args "app/jobs/run_alert_checks_once.py" \
  --secrets \
    "database-url=$DATABASE_URL" \
    "smtp-user=$SMTP_USER" \
    "smtp-pass=$SMTP_PASS" \
    "alert-from=$ALERT_FROM_EMAIL" \
  --env-vars \
    PYTHONPATH=/app \
    DATABASE_URL=secretref:database-url \
    SMTP_USER=secretref:smtp-user \
    SMTP_PASS=secretref:smtp-pass \
    ALERT_FROM_EMAIL=secretref:alert-from \
    SMTP_HOST=smtp.gmail.com \
    SMTP_PORT=587 >/dev/null

echo "[6/7] Recreating prices + news + sentiment jobs..."
recreate_job "stocksense-prices"
az containerapp job create \
  --name stocksense-prices \
  --resource-group "$RG" \
  --environment "$ENV_NAME" \
  --image "$API_IMAGE" \
  --registry-server ghcr.io \
  --registry-username "$GH_USER" \
  --registry-password "$GH_PAT" \
  --trigger-type Schedule \
  --cron-expression "*/15 * * * *" \
  --parallelism 1 \
  --replica-completion-count 1 \
  --replica-retry-limit 1 \
  --replica-timeout 1800 \
  --command "python" \
  --args "app/services/ingesting_pipelines/prices_ingest.py" \
  --secrets "database-url=$DATABASE_URL" \
  --env-vars \
    PYTHONPATH=/app \
    DATABASE_URL=secretref:database-url \
    PRICE_PERIOD=5d \
    PRICE_UPDATE_EXISTING=1 >/dev/null

recreate_job "stocksense-news-ingest"
az containerapp job create \
  --name stocksense-news-ingest \
  --resource-group "$RG" \
  --environment "$ENV_NAME" \
  --image "$API_IMAGE" \
  --registry-server ghcr.io \
  --registry-username "$GH_USER" \
  --registry-password "$GH_PAT" \
  --trigger-type Schedule \
  --cron-expression "0 12,20 * * *" \
  --parallelism 1 \
  --replica-completion-count 1 \
  --replica-retry-limit 1 \
  --replica-timeout 3600 \
  --command "python" \
  --args "app/jobs/run_news_ingest_once.py" \
  --secrets \
    "database-url=$DATABASE_URL" \
    "marketaux-api-token=$MARKETAUX_API_TOKEN" \
    "newsapi-api-key=$NEWSAPI_API_KEY" \
    "alphavantage-api-key=$ALPHAVANTAGE_API_KEY" \
    "guardian-api-key=$GUARDIAN_API_KEY" \
  --env-vars \
    PYTHONPATH=/app \
    DATABASE_URL=secretref:database-url \
    MARKETAUX_API_TOKEN=secretref:marketaux-api-token \
    NEWSAPI_API_KEY=secretref:newsapi-api-key \
    ALPHAVANTAGE_API_KEY=secretref:alphavantage-api-key \
    GUARDIAN_API_KEY=secretref:guardian-api-key \
    NEWS_LOOKBACK_HOURS=24 \
    NEWS_MAX_PAGES_PER_TICKER=1 \
    NEWS_API_LIMIT_PER_PAGE=2 \
    NEWS_MAX_ARTICLES_PER_TICKER=2 \
    NEWSAPI_LOOKBACK_DAYS=1 \
    NEWSAPI_MAX_PAGES=1 \
    NEWSAPI_PAGE_SIZE=2 \
    ALPHAVANTAGE_LOOKBACK_DAYS=1 \
    ALPHAVANTAGE_LIMIT=2 \
    ALPHAVANTAGE_DELAY_SECS=13 \
    GUARDIAN_LOOKBACK_DAYS=1 \
    GUARDIAN_MAX_PAGES=1 \
    GUARDIAN_PAGE_SIZE=2 >/dev/null

recreate_job "stocksense-sentiment-summary"
az containerapp job create \
  --name stocksense-sentiment-summary \
  --resource-group "$RG" \
  --environment "$ENV_NAME" \
  --image "$PIPE_IMAGE" \
  --registry-server ghcr.io \
  --registry-username "$GH_USER" \
  --registry-password "$GH_PAT" \
  --trigger-type Schedule \
  --cron-expression "30 13,21 * * *" \
  --parallelism 1 \
  --replica-completion-count 1 \
  --replica-retry-limit 1 \
  --cpu 2.0 \
  --memory 4.0Gi \
  --replica-timeout 7200 \
  --command "python" \
  --args "app/jobs/run_sentiment_summary_once.py" \
  --secrets \
    "database-url=$DATABASE_URL" \
    "openai-api-key=$OPENAI_API_KEY" \
  --env-vars \
    PYTHONPATH=/app \
    DATABASE_URL=secretref:database-url \
    OPENAI_API_KEY=secretref:openai-api-key \
    FINBERT_TABLES=stock_news_articles \
    FINBERT_ONLY_MISSING=true \
    RETURNS_ONLY_MISSING=1 \
    RETURNS_START_DATE=2020-01-01 \
    AGG_START_DATE=2020-01-01 \
    NEWS_SUMMARY_WINDOWS=7,30 \
    NEWS_SUMMARY_ARTICLE_LIMIT=8 \
    NEWS_SUMMARY_MODEL=gpt-4.1-mini \
    HF_HOME=/cache/huggingface >/dev/null

echo "[7/7] Done. Current jobs:"
az containerapp job list -g "$RG" -o table

echo "Setup complete."
