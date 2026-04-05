# StockSense Deployment on Azure

This guide is for your current setup where GitHub builds images, and Azure deploy is run manually from your machine (no `AZURE_CREDENTIALS` secret required).

## 0) Prerequisites

Install and verify:

```bash
az version
git --version
docker --version
```

Optional:

```bash
gh --version
```

## 1) Create deployment env file (once)

From `ai_roosters/azuredeployment`:

```bash
cd ai_roosters/azuredeployment
cp .deploy.env.example .deploy.env
```

Edit `.deploy.env` and fill in all values.

Load env vars in each new terminal:

```bash
source .deploy.env
```

## 2) One-time infrastructure setup

```bash
cd ai_roosters/azuredeployment
source .deploy.env
bash setup_azure_once.sh
```

What this does:
- checks Azure login and subscription
- creates/updates resource group + Container Apps environment
- creates/updates `stocksense-api`
- recreates jobs:
  - `stocksense-alerts`
  - `stocksense-prices`
  - `stocksense-news-ingest`
  - `stocksense-sentiment-summary`

## 3) Every time you update code

### 3.1 Push code

```bash
git add .
git commit -m "your update message"
git push origin main
```

### 3.2 Let GitHub Actions build/push images

```bash
gh run list --limit 10
```

### 3.3 Manually deploy the new images to Azure

```bash
cd ai_roosters/azuredeployment
source .deploy.env
bash deploy_update.sh
```

This updates the API image and all job images in Azure.

Current scheduled jobs and what they do:
- `stocksense-prices`: price ingestion every 15 minutes.
- `stocksense-news-ingest`: news ingestion twice daily.
- `stocksense-sentiment-summary`: sentiment + summary processing after ingest windows.
- `stocksense-alerts`: alert checks every 5 minutes (if created).

If you still have `stocksense-sentiment`, that is a legacy extra sentiment job and may duplicate work from `stocksense-sentiment-summary`.

## 4) If workflows are unavailable, build/push manually

```bash
cd ai_roosters
source azuredeployment/.deploy.env

docker login ghcr.io -u "$GH_USER" -p "$GH_PAT"

docker build -f backend/API.Dockerfile -t "$API_IMAGE" backend
docker push "$API_IMAGE"

docker build -f backend/Pipeline.Dockerfile -t "$PIPE_IMAGE" backend
docker push "$PIPE_IMAGE"

cd azuredeployment
bash deploy_update.sh
```

## 5) Verify deployment

```bash
cd ai_roosters/azuredeployment
source .deploy.env

API_FQDN=$(az containerapp show --name "$API_APP" --resource-group "$RG" --query properties.configuration.ingress.fqdn -o tsv)
echo "https://$API_FQDN/health"
curl "https://$API_FQDN/health"

az containerapp job list -g "$RG" -o table
az containerapp job execution list --name stocksense-prices --resource-group "$RG" -o table
az containerapp job execution list --name stocksense-news-ingest --resource-group "$RG" -o table
az containerapp job execution list --name stocksense-sentiment-summary --resource-group "$RG" -o table
```

## 6) Troubleshooting

- `Insufficient privileges to complete the operation` while creating service principals:
  - expected on many university tenants
  - use this manual deploy workflow instead of GitHub Azure login
- `ImagePullBackOff`:
  - check `GH_USER`, `GH_PAT`, `API_IMAGE`, `PIPE_IMAGE`
  - rerun `setup_azure_once.sh` to refresh registry credentials
- No recent job runs:
  - `az containerapp job list -g "$RG" -o table`
  - `az containerapp job start --name stocksense-prices --resource-group "$RG"`
