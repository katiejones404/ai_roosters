# File for Deploying on Azure with No Starting Resources

This file was inspired by my student account running out of credits and needed to redeploy on a new account and Azure subscription.

## Step 1: Log out of old account, log into new one

in bash:

`az logout`

`az login`

This will open a browser, sign in with your email that is tied to an Azure subscription with credits.

## Step 2: Get your Subscription ID

`az account show --query id -o tsv`

Copy that value.

## Step 3: Add ID to .deploy.env

Open .deploy.env and update SUBSCRIPTION_ID with the subscription ID. Everything else (RG, ENV_NAME, API_APP, image names, secrets) can stay the same, we are just recreating resources under a new subscription.

If this is the first time you are using the subscription ID, the Container Apps environment needs Log Analytics registered first. Run:

`az provider register -n Microsoft.OperationalInsights --wait`

This will take 1-2 minutes

## Step 4: Run the one-time setup script

`cd ai_roosters/azuredeployment`

`source .deploy.env`

`bash setup_azure_once.sh`

This will create fresh resources (resource group, Container Apps environment, API app, all 4 jobs) in the new account from scratch.

## Step 5: Verify

`API_FQDN=$(az containerapp show --name "$API_APP" --resource-group "$RG" --query properties.configuration.ingress.fqdn -o tsv)`
`curl "https://$API_FQDN/health"`

