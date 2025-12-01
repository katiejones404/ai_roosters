@echo off
echo Starting Stock Sense...

set "ENABLE_KAGGLE_SETUP=false"   REM <-- Set to true if you want Kaggle setup to run
set "USERPROFILE_DIR=%USERPROFILE%"
set "KAGGLE_PATH=%USERPROFILE_DIR%\.kaggle\kaggle.json"

REM  OPTIONAL: KAGGLE SETUP

if /I "%ENABLE_KAGGLE_SETUP%"=="true" (
    echo Checking for Kaggle credentials at:
    echo    %KAGGLE_PATH%
    echo.

    if not exist "%KAGGLE_PATH%" (
        echo ERROR: Kaggle API key not found!
        echo Please place kaggle.json in:
        echo    %KAGGLE_PATH%
        pause
        exit /b
    )

    echo Kaggle credentials found ✓
    echo.

    echo Generating .env file...
    (
        echo KAGGLE_CONFIG=%KAGGLE_PATH%
        echo MEDIASTACK_KEY=5cca6a895185207d783a642ec427ee03
    ) > .env
    echo .env generated
    echo.

:: Download dataset if not already present
if not exist backend\data\reliance-stock-prices-with-news-sentiment-036e93.log (
    echo Downloading Kaggle dataset...
    kaggle kernels output katiejones4/reliance-stock-prices-with-news-sentiment-036e93 -p backend\data

    echo Dataset downloaded 
) else (
    echo Dataset already present. Skipping download.
)

:skip

:: -------------DOCKER SETUP-------------

REM Check if Docker is installed
docker --version >nul 2>&1
if errorlevel 1 (
    echo Docker is not installed. Please install Docker first.
    echo Visit: https://docs.docker.com/get-docker/
    pause
    exit /b 1
)

REM Check if Docker Compose is installed
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo Docker Compose is not installed. Please install Docker Compose first.
    echo Visit: https://docs.docker.com/compose/install/
    pause
    exit /b 1
)

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo Docker is not running. Please start Docker first.
    pause
    exit /b 1
)

echo Docker is ready!

REM Start all services
echo Starting all services...
docker-compose up -d

REM Wait for services to be ready
echo Waiting for services to start...
timeout /t 15 /nobreak >nul

REM Check if services are running
docker-compose ps | findstr "Up" >nul
if errorlevel 1 (
    echo Services failed to start. Check logs with: docker-compose logs
    pause
    exit /b 1
) else (
    echo Services are running!
    echo Your application is available at:
    echo    Frontend:    http://localhost:3000 (React dev server with hot reload)
    echo    Backend API: http://localhost:8000 (FastAPI with auto-reload)
    echo    API Docs:    http://localhost:8000/docs
    echo    Database:    localhost:5433
    echo.
    echo Development mode: Changes to code will auto-reload!
    echo To view logs: docker-compose logs -f
    echo To stop:      docker-compose down
)

pause