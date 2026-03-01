# StockSense - AI-Powered Stock Sentiment Dashboard
live website: [https://ai-roosters-frontend.onrender.com/](https://ai-roosters-webpage.vercel.app/)

To see backend/API health: [https://ai-roosters.onrender.com/](https://stocksense-api-7go1.onrender.com/)
## About Stock Sense 

StockSense is a full-stack web application that helps investors understand how financial news sentiment relates to stock performance. Users can build a personal portfolio, track real price data and historical returns, and read AI-generated summaries that explain what the news sentiment means and why the stock may be performing a certain way.

The core insight the project will ultimately demonstrate is: **does the tone of financial news predict short, medium, and long-term stock returns?** Our project answers this question visually and in plain language for a subset of tickers currently, using a machine learning pipeline built on FinBERT, XGBoost, and GPT.

---

## What We Have Achieved (Current Beta Release)
Underlined points are items that need to be improved in the next release (covered in the TODO section of the ReadME)

### Authentication & User Management
- Full JWT-based authentication: register, _login_, logout, and persistent sessions
- Secure password hashing
- Profile picture upload (stored as base64 in the database)
- _User profile editing: name, phone, username_
- Account deletion with password confirmation

### Portfolio
- Users can add any of the currently supported tickers to their portfolio with quantity and average purchase price
- Real-time display of: current price, cost basis, total gain/loss, 1D / 30D / 120D / 360D returns
- Portfolio comparison mode: select multiple holdings to compare side-by-side with a line chart and metrics table

### Dashboard & Stock Discovery
- Card-based dashboard showing all currently supported tickers with price charts
- Each card displays: current price, 1D/30D/120D/360D return metrics, and _FinBERT sentiment indicators_
- Search by ticker or company name with live filtering
- Trending widget bar chart showing the top 3 holdings from portfolio by 1D return, using existing `return_1d` data already in the portfolio.

### Sentiment Analysis Pipeline (fully run, data in Neon)
- **Article ingestion:** ~40,000+ financial news articles ingested from a HuggingFace dataset (2019–2023) into PostgreSQL
- **FinBERT scoring:** Every article scored with finbert (positive / negative / neutral + confidence probabilities)
- **Stock returns pipeline:** 5+ years of daily price data fetched from yfinance; forward returns (1D/30D/120D/360D) calculated for every trading day
- **Snapshot aggregator:** ~31,000 sentiment snapshots written - one per (ticker, date) - joining article sentiment with stock return data, with XGBoost-predicted returns
- **GPT explanations:** One GPT-4o-mini explanation per ticker, referencing the actual FinBERT sentiment score and realized returns for the 30D / 120D / 360D horizons

### Supported Tickers
AAPL, TSLA, MSFT, GOOGL, AMZN, META, NVDA, JPM, BP, RELIANCE.NS, KSS, ALK, NVS, AXP, MRK

### Deployment
- Frontend deployed on Vercel
- Backend deployed on Render(FastAPI web service)
- Database hosted on Neon (serverless PostgreSQL)
- All data already in Neon (new deployments work immediately without running the pipeline)

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, TypeScript, Vite, React Router 7, Recharts |
| Backend API | Python 3.11, FastAPI 0.95, SQLAlchemy 1.4, psycopg2 |
| Auth | JWT (python-jose), bcrypt (passlib) |
| Database | PostgreSQL 15 (local Docker) / Neon (hosted) |
| ML - Sentiment | ProsusAI/finbert (HuggingFace Transformers) |
| ML - Prediction | XGBoost, scikit-learn |
| Price Data | yfinance |
| GPT Explanations | OpenAI GPT-4o-mini (via REST API) |
| Containers | Docker, Docker Compose |
| Hosting | Render (API), Vercel(Frontend) ,Neon (Database) |

---

## Prerequisites - Software to Install

You need the following before running locally:

### 1. Git
```bash
git --version
```
Download: https://git-scm.com/downloads

### 2. Docker Desktop
Runs the entire app (API, database, frontend) in containers. No separate Python or Node.js install needed.

- Download: https://www.docker.com/products/docker-desktop/
- **Windows/Mac:** Install Docker Desktop and make sure it is **running** (whale icon in system tray)
- **Linux:** Install Docker Engine + Docker Compose plugin
```bash
docker --version && docker compose version
```

> If you want to run tests or the pipeline **outside** Docker, you also need:

### 3. Python 3.11 (tests / pipeline outside Docker only)
Download: https://www.python.org/downloads/
On Windows, check **"Add Python to PATH"** during install.
```bash
python --version   # verify
```

---

## Deploying Locally from Scratch

### Step 1 - Clone the repository

```bash
git clone git@github.com:SCCapstone/ai_roosters.git
cd ai_roosters/debug_ai_roosters
```

> If you get a permission error, add your SSH key to GitHub.
> See: https://docs.github.com/en/authentication/connecting-to-github-with-ssh

### Step 2 - Create your `.env` file. 
Note, there are additional .env files. Check all .env.example files in the repo.

```bash
# Mac / Linux
cp .env.example .env

# Windows (PowerShell)
Copy-Item .env.example .env
```

Open `.env` in a text editor. 

For local development using the local PostgreSQL container, the defaults work without any changes.

To use the **hosted Neon database**, replace `DATABASE_URL` with your Neon connection string:
```
DATABASE_URL=postgresql://...
```

Optional keys (only needed if running the ML pipeline):
```
OPENAI_API_KEY=sk-proj-...        # only needed for GPT explanations
HUGGINGFACE_HUB_TOKEN=hf_...     # only needed for article ingestion
ENABLE_GPT_EXPLANATIONS=0         # set to 1 to run GPT when pipeline runs
```

### Step 3 - Start the app

Make sure Docker Desktop is open on your computer

```bash
docker compose up api frontend
```

On first run (or after changing `requirements-api.txt` or the Dockerfile), add `--build` to rebuild the images:

```bash
docker compose up api frontend --build
```

The first build takes 3–5 minutes (downloading images and installing packages). Subsequent runs start quickly.

When the API prints `Application startup complete`, the app is ready:

| Service | URL |
|---------|-----|
| Frontend (React) | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Swagger API docs | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |

On first startup, the API automatically:
1. Creates all database tables (idempotent - safe to run again)
2. Fetches the last 30 days of stock price data from yfinance (or full history from 2020 if the DB is empty)

> **If you have not ran the pipeline before**, you will need to run the pipeline (see below) to populate sentiment data.

### Step 4 - Stop the app

```bash
# Stop containers, keep database data
docker compose down

# Stop AND delete all data (full reset)
docker compose down -v
```

### Step 5 - Rebuild after code changes

Python and frontend code changes apply automatically via hot reload (no rebuild needed).
If you change `requirements-api.txt`, `requirements-pipeline.txt`, or any Dockerfile:
```bash
docker compose up --build
```

---

## Running the ML Pipeline from Scratch

The pipeline populates the `articles`, `stocks`, and `sentiment_snapshots` tables. It only needs to be run once currently.

The pipeline has 5 steps that must be run in order:

### Step 1 - Ingest articles (HuggingFace dataset -> `articles` table)

> **Recommended:** Use the Colab notebook `notebooks/news_ingest_colab_v2.ipynb` to run article ingestion on Google Colab (faster, no local GPU needed). If you are a student, you have access to Colab pro for free, which can cut down your run time significantly. Set `DATABASE_URL` and `HF_TOKEN` as Colab secrets.

Or use:

```bash
docker compose --profile pipeline run --rm pipeline \
  python -m app.services.ingesting_pipelines.news_ingest
```

This downloads articles from `Brianferrell787/financial-news-multisource` on HuggingFace and inserts them into the `articles` table. Requires `HUGGINGFACE_HUB_TOKEN` in `.env`. This option can take a lot of run time for all data in the HuggingFace dataset (which has 57M+ rows). Use Colab for quick, articles that are filtered for relevancy.

### Step 2 - Score articles with FinBERT (`articles` table -> sentiment fields)

```bash
docker compose --profile pipeline run --rm pipeline \
  python -m app.services.sentiment.article_processing
```

Runs finbert on 5000 unscored articles. Adds `sentiment`, `sentiment_score`, `prob_pos`, `prob_neg`, `prob_neu` to each row. This step is slow on CPU. GPU recommended - use Google Colab if available (code not in notebook).

### Step 3 - Ingest stock price data (`stocks` table)

```bash
docker compose --profile pipeline run --rm pipeline \
  python -m app.services.ingesting_pipelines.prices_ingest
```

Fetches daily data from yfinance for all supported tickers (2020–present) and calculates forward returns (1D / 30D / 120D / 360D).

> The API also runs this automatically on startup (Step 3 is optional if the API has already run).

### Step 4 - Run the snapshot aggregator + XGBoost (`sentiment_snapshots` table)

```bash
docker compose --profile pipeline run --rm pipeline \
  python -m app.services.sentiment.aggregator
```

Joins article sentiment with stock price data to build one snapshot per (ticker, date). Trains and runs XGBoost to produce predicted returns. Writes ~32,000 rows to `sentiment_snapshots`.

### Step 5 - Generate GPT explanations (optional)

Set `ENABLE_GPT_EXPLANATIONS=1` in `.env` and provide a valid `OPENAI_API_KEY`, then:

```bash
docker compose --profile pipeline run --rm pipeline \
  python -c "
from app.services.sentiment.aggregator import run_gpt_explanations
run_gpt_explanations()
"
```

This calls GPT-4o-mini once per ticker to generate plain-language explanations linking sentiment to realized returns. Results are stored in `gpt_expl_30d`, `gpt_expl_120d`, `gpt_expl_360d` on `sentiment_snapshots`.

> **Re-running GPT after changes:** If you need to regenerate GPT explanations, first null out the existing ones in SQL:
> ```sql
> UPDATE sentiment_snapshots
> SET gpt_expl_30d = NULL, gpt_expl_120d = NULL, gpt_expl_360d = NULL,
>     gpt_model = NULL, gpt_generated_at = NULL
> WHERE num_articles = 0;
> ```
> Then re-run the GPT command above.

---

## How the Live Website is Deployed

The production app uses three services:

### Database - Neon (serverless PostgreSQL)
- Free-tier Neon project
- All pipeline data (articles, stocks, sentiment_snapshots, GPT explanations) were written directly to Neon by running the pipeline locally with the Neon `DATABASE_URL`
- Tables are created automatically by `db_init.py` on first API startup

### Backend API - Render Web Service
- Deployed from the GitHub repo main branch - Render automatically redeploys on every push
- Render is configured to install dependencies from `requirements-api.txt` and start the server with uvicorn
- Environment variables (`DATABASE_URL`, `SECRET_KEY`, `OPENAI_API_KEY`, `ENABLE_GPT_EXPLANATIONS`) are set in the Render dashboard
- On startup the API runs `init_db()` (creates tables if missing) and refreshes the last 30 days of price data

### Frontend - Vercel
- Deployed on Vercel, connected to the GitHub repo - Vercel automatically builds and deploys on every push to main in 'ai_roosters_'
- `VITE_API_BASE_URL` is set to the Render backend URL via `frontend/.env.production` (read at build time by Vite)

### Keeping the API Alive
Render free-tier services spin down after 15 minutes of inactivity. To prevent cold starts during demos:
- UptimeRobot is configured to ping 'https://stocksense-api-7go1.onrender.com/' every 5–10 minutes

---

## TODO: Next Steps

**The following features and improvements are planned or recommended for future development**

- **Login Bug:** - On the deployed website, sometimes the user has to click the login button twice to log in. We are not sure what is causing this, but we would like to fix it before the next milestone.
- **Finbert Sentiment Indicators** - We would like to improve our sentiment indicators. We plan on  doing this by gathering more recent article sources, improving our sentiment gathering pipeline, and restructuring our pipeline to make the sentiment more accurate.
- **More recent article data:** Ingest 2024–2025 articles from different subsets of the HuggingFace dataset, re-run FinBERT, and update the snapshot aggregator to produce more current sentiment snapshots. The current pipeline data ends in late 2023.
- **More tickers:** The pipeline is not ticker-specific. Adding new tickers only requires adding them to the price ingest list and running the returns + aggregator pipeline again.
- **Automated pipeline refresh:** Schedule a weekly pipeline run (like via Render Cron Job or GitHub Actions) to keep price data and sentiment snapshots current without manual intervention
- **Improved GPT prompt:** A more detailed prompt has been drafted (using formatted % returns, FinBERT score, and positive/negative article percentages), but we not be utilized until we are able to improve our pipeline process.
- **Wired-up Settings page:** The Settings page UI is complete but the save buttons do not yet call the backend perfectly. 
- **Username change:** Add functionality to the username change option.
- **Add stock by purchase date:** Users who have stock previous put in their portfolio can select the date at which they purchased the stock. Our app will match the price from that date to make their porfolio more accurate.


---

---

## Core Files/Folders Project Structure

```
debug_ai_roosters/
  backend/
    app/
      api/                   # FastAPI route handlers (auth, portfolio, stocks, sentiment, news)
      core/                  # JWT creation/verification, bcrypt password hashing
      db/
        init/                # SQL schema init (runs via db_init.py on startup, safe to re-run)
      models/                # SQLAlchemy ORM models (User, Portfolio)
      schema/                # Pydantic request/response schemas
      services/
        ingesting_pipelines/ # yfinance price ingestor, HuggingFace article ingestor
        sentiment/           # FinBERT pipeline, returns pipeline, aggregator + GPT
    requirements-api.txt     # Slim API dependencies (no ML libraries)
    requirements-pipeline.txt# Full ML stack (torch, transformers, xgboost)
    API.Dockerfile           # Lightweight API container (fast build)
    Pipeline.Dockerfile      # Full ML container (used for pipeline steps)
  frontend/
    src/
      api/                   # API client functions
      components/            # Navbar, shared UI components
      utils/                 # Auth utilities, stock name map
      Dashboard.tsx          # Main stock discovery page
      portfolio.tsx          # Personal portfolio page
      StockDetail.tsx        # Individual stock + sentiment detail
      settings.tsx           # User profile and security settings
      login.tsx              # Login page
      create_account.tsx     # Registration page
    Frontend.Dockerfile
  notebooks/
    ai_roosters_pipeline.ipynb    # Colab pipeline runner (full ML pipeline)
    news_ingest_colab_v2.ipynb    # Colab article ingestion helper
  Testing/
    User/                    # Auth and user management tests
    Portfolio/               # Portfolio API tests
    Sentiment/               # Sentiment pipeline unit + tests
    Stocks/                  # Stock price data tests
    Articles/                # Article ingestion tests
  docker-compose.yml
  .env.example
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register a new user |
| POST | `/api/auth/login` | Log in, receive JWT |
| POST | `/api/auth/logout` | Invalidate session |
| GET | `/api/auth/me` | Get current user profile |
| PATCH | `/api/auth/me` | Update name, username, or phone |
| PATCH | `/api/auth/me/password` | Change password |
| DELETE | `/api/auth/me` | Delete account (requires password) |
| POST | `/api/auth/me/picture` | Upload profile picture |
| GET | `/api/portfolio/` | Get user's portfolio with return data |
| POST | `/api/portfolio/` | Add a stock to portfolio |
| DELETE | `/api/portfolio/{id}` | Remove a stock from portfolio |
| GET | `/api/stocks/` | List all available tickers |
| GET | `/api/stocks/{ticker}/prices` | Get price history for a ticker |
| GET | `/api/sentiment/{ticker}` | Get sentiment snapshot + GPT explanations |
| GET | `/health` | Health check (used by uptime monitor) |

---

## Running Tests

Tests live under the `Testing/` directory.

```bash
# Install test dependencies
pip install -r backend/requirements-api.txt

# Run all tests (pytest + behave)
python run_testing.py

# Pytest only
python run_testing.py --no-behave

# Behave (BDD) only
python run_testing.py --behave-only

# Run a specific test group
python run_testing.py Testing/User -v
python run_testing.py Testing/Portfolio -v
python run_testing.py Testing/Sentiment/unit -v
```

---

## Authors

Connor Thiele — cthiele@email.sc.edu

Katie Jones — Katie.jones4@outlook.com

Sofia Bacha — sofbacha01@gmail.com

Kevin Do — kdox1023@gmail.com

Andrew Lim — andrew.lim0023@gmail.com

