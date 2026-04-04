Param(
    [ValidateSet("setup", "set-price", "run-check", "status", "cleanup")]
    [string]$Action = "status",
    [string]$Email = "airooster492@gmail.com",
    [string]$Ticker = "ALRTT",
    [double]$TargetPrice = 100.0,
    [ValidateSet("above", "below")]
    [string]$Direction = "above",
    [double]$Price = 0,
    [string]$AlertId = "",
    [switch]$NoEmailNotify,
    [switch]$ForceEnableNotifications,
    [switch]$DeleteUser
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
$scriptPathInContainer = "/app/Testing/Alerts/manual_alert_test.py"

function Invoke-AlertScript {
    Param(
        [Parameter(Mandatory = $true)]
        [string[]]$CommandArgs
    )
    $dbTesting = [Environment]::GetEnvironmentVariable("DATABASE_URL_TESTING")
    if ([string]::IsNullOrWhiteSpace($dbTesting)) {
        docker compose exec api python $scriptPathInContainer @CommandArgs
    } else {
        docker compose exec -e DATABASE_URL_TESTING="$dbTesting" api python $scriptPathInContainer @CommandArgs
    }
}

switch ($Action) {
    "setup" {
        $commandArgs = @(
            "setup",
            "--email", $Email,
            "--ticker", $Ticker,
            "--target-price", "$TargetPrice",
            "--direction", $Direction
        )
        if ($NoEmailNotify) {
            $commandArgs += "--no-email-notify"
        }
        if ($ForceEnableNotifications) {
            $commandArgs += "--force-enable-notifications"
        }
        Push-Location $repoRoot
        try {
            Invoke-AlertScript -CommandArgs $commandArgs
        } finally {
            Pop-Location
        }
    }
    "set-price" {
        if ($Price -le 0) {
            throw "Price must be > 0 for set-price."
        }
        Push-Location $repoRoot
        try {
            Invoke-AlertScript -CommandArgs @("set-price", "--ticker", $Ticker, "--price", "$Price")
        } finally {
            Pop-Location
        }
    }
    "run-check" {
        Push-Location $repoRoot
        try {
            Invoke-AlertScript -CommandArgs @("run-check")
        } finally {
            Pop-Location
        }
    }
    "status" {
        Push-Location $repoRoot
        try {
            if ($AlertId) {
                Invoke-AlertScript -CommandArgs @("status", "--alert-id", $AlertId, "--ticker", $Ticker)
            } else {
                Invoke-AlertScript -CommandArgs @("status", "--ticker", $Ticker)
            }
        } finally {
            Pop-Location
        }
    }
    "cleanup" {
        $commandArgs = @("cleanup", "--email", $Email, "--ticker", $Ticker)
        if ($DeleteUser) {
            $commandArgs += "--delete-user"
        }
        Push-Location $repoRoot
        try {
            Invoke-AlertScript -CommandArgs $commandArgs
        } finally {
            Pop-Location
        }
    }
}
