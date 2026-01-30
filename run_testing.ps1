Param(
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$PytestArgs
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

# Prefer local venv if present
$venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (Test-Path $venvPython) {
    $pythonExe = $venvPython
} else {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        Write-Error "Python not found. Create/activate a venv or install Python."
        exit 1
    }
    $pythonExe = $pythonCmd.Source
}

# Make backend imports available (app.* lives under Backend/app)
$backendPath = Join-Path $repoRoot 'Backend'
$existing = $env:PYTHONPATH
if ([string]::IsNullOrWhiteSpace($existing)) {
    $env:PYTHONPATH = "$backendPath;$repoRoot"
} else {
    $env:PYTHONPATH = "$backendPath;$repoRoot;$existing"
}

# Default args if none provided
if (-not $PytestArgs -or $PytestArgs.Count -eq 0) {
    $PytestArgs = @('Testing', '-v', '--tb=short')
} else {
    # If the caller didn't pass a path, default to Testing
    $hasPath = $false
    foreach ($a in $PytestArgs) {
        if ($a -and -not $a.StartsWith('-')) { $hasPath = $true; break }
    }
    if (-not $hasPath) {
        $PytestArgs = @('Testing') + $PytestArgs
    }
}

Write-Host "Using Python: $pythonExe"
Write-Host "Running: $pythonExe -m pytest $($PytestArgs -join ' ')"

& $pythonExe -m pytest @PytestArgs
exit $LASTEXITCODE
