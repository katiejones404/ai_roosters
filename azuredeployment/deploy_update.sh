#!/usr/bin/env bash
set -euo pipefail

if [[ -f .deploy.env ]]; then
  # shellcheck disable=SC1091
  source .deploy.env
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

az account show >/dev/null 2>&1 || az login >/dev/null
az account set --subscription "$SUBSCRIPTION_ID"

echo "Updating API image..."
az containerapp update \
  --name "$API_APP" \
  --resource-group "$RG" \
  --image "$API_IMAGE" >/dev/null

echo "Updating job images..."
az containerapp job update --name stocksense-alerts --resource-group "$RG" --image "$API_IMAGE" >/dev/null
az containerapp job update --name stocksense-prices --resource-group "$RG" --image "$API_IMAGE" >/dev/null
az containerapp job update --name stocksense-news-ingest --resource-group "$RG" --image "$API_IMAGE" >/dev/null
az containerapp job update --name stocksense-sentiment-summary --resource-group "$RG" --image "$PIPE_IMAGE" >/dev/null

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
