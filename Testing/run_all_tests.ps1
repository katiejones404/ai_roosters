Param(
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$PytestArgs
)

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
& (Join-Path $repoRoot 'run_testing.ps1') @PytestArgs
exit $LASTEXITCODE
