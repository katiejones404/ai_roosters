@echo off
setlocal
set REPO_ROOT=%~dp0
powershell -NoProfile -ExecutionPolicy Bypass -File "%REPO_ROOT%run_testing.ps1" %*
exit /b %ERRORLEVEL%
