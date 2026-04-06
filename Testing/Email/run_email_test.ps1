Param(
    [ValidateSet("verify-smtp", "send-alert", "send-reset")]
    [string]$Action = "verify-smtp",
    [string]$Email = "",
    [string]$Ticker = "AAPL",
    [ValidateSet("above", "below")]
    [string]$Direction = "above",
    [double]$TargetPrice = 200.0,
    [double]$CurrentPrice = 210.0,
    [string]$ResetLink = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
$scriptPathInContainer = "/app/Testing/Email/manual_email_test.py"

function Invoke-EmailScript {
    Param(
        [Parameter(Mandatory = $true)]
        [string[]]$CommandArgs
    )
    docker compose exec api python $scriptPathInContainer @CommandArgs
}

switch ($Action) {
    "verify-smtp" {
        Push-Location $repoRoot
        try {
            Invoke-EmailScript -CommandArgs @("verify-smtp")
        } finally {
            Pop-Location
        }
    }
    "send-alert" {
        if ([string]::IsNullOrWhiteSpace($Email)) {
            throw "Email is required for send-alert. Use -Email your@email.com"
        }
        $commandArgs = @(
            "send-alert",
            "--email", $Email,
            "--ticker", $Ticker,
            "--direction", $Direction,
            "--target-price", "$TargetPrice",
            "--current-price", "$CurrentPrice"
        )
        Push-Location $repoRoot
        try {
            Invoke-EmailScript -CommandArgs $commandArgs
        } finally {
            Pop-Location
        }
    }
    "send-reset" {
        if ([string]::IsNullOrWhiteSpace($Email)) {
            throw "Email is required for send-reset. Use -Email your@email.com"
        }
        $commandArgs = @("send-reset", "--email", $Email)
        if (-not [string]::IsNullOrWhiteSpace($ResetLink)) {
            $commandArgs += @("--reset-link", $ResetLink)
        }
        Push-Location $repoRoot
        try {
            Invoke-EmailScript -CommandArgs $commandArgs
        } finally {
            Pop-Location
        }
    }
}
