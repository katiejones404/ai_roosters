Param(
    [ValidateSet("all", "testing", "backend", "unit", "behavioral", "raw-all")]
    [string]$Suite = "all",

    [ValidateSet("docker", "local")]
    [string]$Mode = "docker",

    [switch]$Build,
    [switch]$NoStart,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PytestArgs = @()
)

$ErrorActionPreference = "Stop"

$testingRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $testingRoot
$backendRoot = Join-Path $repoRoot "Backend"
$lastTestExitCode = 0

$unitTargets = @(
    "Testing/Alerts/test_alerts_logic_unit.py",
    "Testing/Alerts/test_alert_scheduler_unit.py",
    "Testing/Email/unit",
    "Testing/Networth/unit",
    "Testing/News/unit",
    "Testing/Portfolio/unit",
    "Testing/Sentiment/unit/test_sentiment_api_unit.py",
    "Testing/Sentiment/unit/test_sentiment_logic_unit.py",
    "Testing/Stocks/unit",
    "Testing/User/unit"
)

$behavioralTargets = @(
    "Testing/Alerts/behavioral",
    "Testing/Email/behavioral",
    "Testing/Networth/behavioral",
    "Testing/News/behavioral",
    "Testing/Portfolio/behavioral",
    "Testing/Stocks/behavior",
    "Testing/User/behavioral"
)

function Convert-TestTarget {
    Param(
        [Parameter(Mandatory = $true)]
        [string]$RelativePath
    )

    if ($Mode -eq "docker") {
        $normalized = $RelativePath.Replace("\", "/")
        if ($normalized.StartsWith("Backend/")) {
            return "/app/" + $normalized.Substring("Backend/".Length)
        }
        return "/app/" + $normalized
    }

    $localPath = $RelativePath.Replace("/", [IO.Path]::DirectorySeparatorChar)
    return Join-Path $repoRoot $localPath
}

function Get-PytestTargets {
    switch ($Suite) {
        "all" {
            return @(
                ($unitTargets | ForEach-Object { Convert-TestTarget $_ })
                ($behavioralTargets | ForEach-Object { Convert-TestTarget $_ })
                (Convert-TestTarget "Backend/tests")
            )
        }
        "testing" {
            return @(
                ($unitTargets | ForEach-Object { Convert-TestTarget $_ })
                ($behavioralTargets | ForEach-Object { Convert-TestTarget $_ })
            )
        }
        "backend" {
            return @((Convert-TestTarget "Backend/tests"))
        }
        "unit" {
            return $unitTargets | ForEach-Object { Convert-TestTarget $_ }
        }
        "behavioral" {
            return $behavioralTargets | ForEach-Object { Convert-TestTarget $_ }
        }
        "raw-all" {
            return @(
                (Convert-TestTarget "Testing"),
                (Convert-TestTarget "Backend/tests")
            )
        }
    }
}

function Get-BehaveTargets {
    if ($Suite -in @("all", "testing", "behavioral", "raw-all")) {
        return @((Convert-TestTarget "Testing/Sentiment/behavioral"))
    }
    return @()
}

function Invoke-Pytest {
    Param(
        [AllowEmptyCollection()]
        [string[]]$Targets = @()
    )

    if ($Targets.Count -eq 0) {
        $script:lastTestExitCode = 0
        return
    }

    Write-Host ""
    Write-Host "Running pytest suite '$Suite' in $Mode mode..." -ForegroundColor Cyan

    if ($Mode -eq "docker") {
        $dockerArgs = @("compose", "exec", "api", "python", "-m", "pytest") + $Targets + @("-v", "-ra") + $PytestArgs
        & docker @dockerArgs
        $script:lastTestExitCode = $LASTEXITCODE
        return
    }

    $pythonArgs = @("-m", "pytest") + $Targets + @("-v", "-ra") + $PytestArgs
    & python @pythonArgs
    $script:lastTestExitCode = $LASTEXITCODE
}

function Invoke-Behave {
    Param(
        [AllowEmptyCollection()]
        [string[]]$Targets = @()
    )

    if ($Targets.Count -eq 0) {
        $script:lastTestExitCode = 0
        return
    }

    Write-Host ""
    Write-Host "Running behave suite for sentiment behavioral tests..." -ForegroundColor Cyan

    if ($Mode -eq "docker") {
        $dockerArgs = @("compose", "exec", "api", "python", "-m", "behave") + $Targets
        & docker @dockerArgs
        $script:lastTestExitCode = $LASTEXITCODE
        return
    }

    $pythonArgs = @("-m", "behave") + $Targets
    & python @pythonArgs
    $script:lastTestExitCode = $LASTEXITCODE
}

function Write-TestResult {
    Param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [int]$ExitCode
    )

    if ($ExitCode -eq 0) {
        Write-Host "$Name passed." -ForegroundColor Green
    } else {
        Write-Host "$Name failed with exit code $ExitCode." -ForegroundColor Red
    }
}

Push-Location $repoRoot
try {
    if ($Mode -eq "docker") {
        if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
            throw "Docker was not found. Install Docker Desktop, or run unit tests with: .\Testing\run_all_tests.ps1 -Suite unit -Mode local"
        }

        if (-not $NoStart) {
            Write-Host "Starting Docker services..." -ForegroundColor Cyan
            $composeArgs = @("compose", "up", "-d")
            if ($Build) {
                $composeArgs += "--build"
            }
            $composeArgs += "api"
            & docker @composeArgs
            if ($LASTEXITCODE -ne 0) {
                exit $LASTEXITCODE
            }
        }
    } else {
        if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
            throw "Python was not found on PATH."
        }

        $oldPythonPath = $env:PYTHONPATH
        $pathParts = @($backendRoot, $repoRoot)
        if (-not [string]::IsNullOrWhiteSpace($oldPythonPath)) {
            $pathParts += $oldPythonPath
        }
        $env:PYTHONPATH = $pathParts -join [IO.Path]::PathSeparator
    }

    $pytestTargets = @(Get-PytestTargets)
    $behaveTargets = @(Get-BehaveTargets)

    Invoke-Pytest -Targets $pytestTargets
    $pytestExitCode = $script:lastTestExitCode

    Invoke-Behave -Targets $behaveTargets
    $behaveExitCode = $script:lastTestExitCode

    if ($Mode -eq "local") {
        $env:PYTHONPATH = $oldPythonPath
    }

    Write-Host ""
    Write-Host "Test run summary" -ForegroundColor Cyan
    Write-TestResult -Name "pytest" -ExitCode $pytestExitCode
    if ($behaveTargets.Count -gt 0) {
        Write-TestResult -Name "behave" -ExitCode $behaveExitCode
    }

    if ($pytestExitCode -ne 0) {
        exit $pytestExitCode
    }
    if ($behaveExitCode -ne 0) {
        exit $behaveExitCode
    }

    Write-Host ""
    Write-Host "All requested tests passed." -ForegroundColor Green
    exit 0
} finally {
    if ($Mode -eq "local") {
        $env:PYTHONPATH = $oldPythonPath
    }
    Pop-Location
}
