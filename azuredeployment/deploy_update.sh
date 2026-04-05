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

for v in SUBSCRIPTION_ID RG API_APP GH_USER GH_PAT API_IMAGE PIPE_IMAGE; do
  require_var "$v"
done

echo "Using deployment env file: $ENV_FILE"
az account show >/dev/null 2>&1 || az login >/dev/null
az account set --subscription "$SUBSCRIPTION_ID"

echo "Updating API image..."
az containerapp update \
  --name "$API_APP" \
  --resource-group "$RG" \
  --image "$API_IMAGE" >/dev/null

update_job_image_if_exists() {
  local job_name="$1"
  local image="$2"

  if az containerapp job show --name "$job_name" --resource-group "$RG" >/dev/null 2>&1; then
    az containerapp job update --name "$job_name" --resource-group "$RG" --image "$image" >/dev/null
    echo "Updated job image: $job_name"
  else
    echo "Skipped missing job: $job_name"
  fi
}

echo "Updating job images..."
update_job_image_if_exists "stocksense-alerts" "$API_IMAGE"
update_job_image_if_exists "stocksense-prices" "$API_IMAGE"
update_job_image_if_exists "stocksense-news-ingest" "$API_IMAGE"
update_job_image_if_exists "stocksense-sentiment" "$PIPE_IMAGE"
update_job_image_if_exists "stocksense-sentiment-summary" "$PIPE_IMAGE"

echo "Deployment update complete."

echo "\nAPI health endpoint:"
API_FQDN=$(az containerapp show --name "$API_APP" --resource-group "$RG" --query properties.configuration.ingress.fqdn -o tsv)
echo "https://$API_FQDN/health"

echo "\nJobs:"
az containerapp job list -g "$RG" -o table

echo "\nRecent executions:"
az containerapp job execution list --name stocksense-prices --resource-group "$RG" -o table || true
az containerapp job execution list --name stocksense-news-ingest --resource-group "$RG" -o table || true
az containerapp job execution list --name stocksense-sentiment-summary --resource-group "$RG" -o table || true
