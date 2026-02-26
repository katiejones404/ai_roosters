(Not fully integrated with Beta Milestone features as of 02/26/2026)
frontend: [https://ai-roosters-frontend.onrender.com/](https://ai-roosters-webpage.vercel.app/)

To see backend/API health:
backend: [https://ai-roosters.onrender.com/](https://stocksense-api-7go1.onrender.com/)
## Stock Sense 

StockSense is a full-stack web application that provides investors with an AI-driven platform to track stock performance, analyze sentiment trends, and manage personalized portfolios. It integrates both quantitative (price and performance) and qualitative (news sentiment) data using a modern, containerized architecture. The project uses AI (FinBERT) to classify financial news articles as positive, neutral, or negative and correlates that sentiment with historical stock price movements.

## What it does

- Users register, log in, and build a personal portfolio of stocks
- The app displays current price, cost basis, gain/loss, and historical returns (1D / 30D / 120D / 360D) for each holding
- News sentiment data (scored by FinBERT) is aggregated per ticker per day and shown alongside price data
- Users can visualize their portfolio and compare stocks side-by-side

**Supported tickers:**(Add here when finalized)


---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, TypeScript, Vite, React Router |
| Backend API | Python 3.11, FastAPI, SQLAlchemy 1.4, psycopg2 |
| Auth | JWT (python-jose), bcrypt |
| Database | PostgreSQL 15 (local) / Neon (hosted) |
| ML Pipeline | FinBERT (ProsusAI/finbert), XGBoost, scikit-learn |
| Price Data | yfinance |
| Containers | Docker, Docker Compose |

---

## Prerequisites — software to install

You need the following installed before running anything locally:

### 1. Git
Used to clone the repository.
- Download: https://git-scm.com/downloads
- Verify: `git --version`

### 2. Docker Desktop
Used to run the entire app (API, database, frontend) in containers. No need to install Python or Node.js separately.
- Download: https://www.docker.com/products/docker-desktop/
- **Windows/Mac:** Install Docker Desktop and make sure it is **running** (look for the whale icon in your system tray)
- **Linux:** Install Docker Engine + Docker Compose plugin
- Verify: `docker --version` and `docker compose version`

> If you want to run tests or the pipeline **outside** of Docker, you also need:

### 3. Python 3.11 (for tests / pipeline only)
- Download: https://www.python.org/downloads/
- During install on Windows, check **"Add Python to PATH"**
- Verify: `python --version`

### 4. Node.js 18+ (for frontend outside Docker only)
- Download: https://nodejs.org/
- Verify: `node --version` and `npm --version`

---

## Running locally with Docker

Docker is the recommended way to run the full app locally. It handles Python, Node.js, and PostgreSQL for you.

### Step 1 — Clone the repo

```bash
git clone git@github.com:SCCapstone/ai_roosters.git
cd ai_roosters/debug_ai_roosters
```

> If you get a permission error, make sure your SSH key is added to your GitHub account.
> See: https://docs.github.com/en/authentication/connecting-to-github-with-ssh

### Step 2 — Set up environment variables

```bash
# Mac / Linux
cp .env.example .env

# Windows (Command Prompt)
copy .env.example .env

# Windows (PowerShell)
Copy-Item .env.example .env
```

Open `.env` in a text editor. For local development **no changes are needed** — the defaults connect to the local PostgreSQL container that Docker starts automatically.

> To use a hosted Neon database instead of the local one, replace `DATABASE_URL` with your Neon connection string.

### Step 3 — Build and start all containers

```bash
docker-compose up --build
```

The first build takes 3–5 minutes (downloading base images and installing packages).
Subsequent runs are faster because Docker caches layers.

Once running, you will see logs from all services. When the API prints `Application startup complete`, everything is ready.

| Service | URL |
|---------|-----|
| Frontend (React) | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |

On first startup the API automatically:
1. Creates all database tables
2. Ingests 5 years of stock price data from yfinance for all 10 tickers

### Step 4 — Stop the app

```bash
# Stop containers (keeps database data)
docker-compose down

# Stop AND delete all data (full reset)
docker-compose down -v
```

### Step 5 — Rebuild after code changes

If you change Python dependencies or Docker configuration:
```bash
docker-compose up --build
```

For code-only changes, the containers use volume mounts with `--reload` so changes apply automatically without rebuilding.

---

## Running without Docker (frontend only)

If you only want to run the frontend locally against the deployed Render API:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The frontend will talk to the live Render API by default (configured in `frontend/.env.production`).

---

## Running the ML sentiment pipeline (optional)

The sentiment pipeline scores financial news articles with FinBERT and populates the `articles` and `sentiment_snapshots` tables. This is separate from the API and only needs to run once.

**Recommended: run in Google Colab** (free GPU, faster than CPU).
See `notebooks/ai_roosters_pipeline.ipynb` for the full notebook with instructions.

To run locally with Docker (CPU only, slow):

```bash
docker-compose --profile pipeline up pipeline
```

Or run a specific pipeline script:

```bash
docker-compose --profile pipeline run pipeline python -m app.services.sentiment.article_processing
```

> Note: The pipeline requires article data (CSV with columns: `published_at, title, description, url`).
> The API works without sentiment data — portfolio and price features function normally.

---

## Running the Jupyter notebook

```bash
docker-compose up notebook
```

Open http://localhost:8888 in your browser.

---

## Project structure

```
debug_ai_roosters/
  backend/
    app/
      api/              # FastAPI route handlers (auth, portfolio, stocks, sentiment)
      core/             # JWT security, password hashing
      db/               # SQLAlchemy engine, init SQL scripts (can be safely reran)
      models/           # models (User, Portfolio)
      schema/           # Pydantic request/response schemas
      services/
        ingesting_pipelines/   # yfinance price ingestor
        sentiment/             # FinBERT pipeline, aggregator
    requirements-api.txt       # Slim API dependencies (no ML)
    requirements-pipeline.txt  # Full ML stack
    API.Dockerfile             # Lightweight API container
    Pipeline.Dockerfile        # Full ML container
    Backend.Dockerfile         # Full stack (for notebook)
  frontend/
    src/               # React components and pages
    Frontend.Dockerfile
  notebooks/
    ai_roosters_pipeline.ipynb  # Google Colab pipeline runner
  docker-compose.yml
  .env.example
```

---

## API endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register a new user |
| POST | `/api/auth/login` | Log in, receive JWT |
| POST | `/api/auth/logout` | Invalidate token |
| GET | `/api/auth/me` | Get current user profile |
| DELETE | `/api/auth/me` | Delete account (requires password) |
| GET | `/api/portfolio/` | Get user's portfolio |
| POST | `/api/portfolio/` | Add a stock to portfolio |
| DELETE | `/api/portfolio/{id}` | Remove a stock |
| GET | `/api/stocks/` | List available stocks |
| GET | `/api/sentiment/{ticker}` | Get sentiment data for a ticker |
| GET | `/health` | Health check |

---

## Testing

### Where the tests are

- Pytest tests (unit + API/behavior-style) live under `Testing/`.
- Sentiment behavioral (BDD) tests live under `Testing/Sentiment/behavioral/` and run with `behave`.

### Install test dependencies

From the repo root:

```bash
pip install -r ./Backend/requirements.txt
```

### Run ALL tests (pytest + sentiment behave)

From the repo root:

```bash
python ./run_testing.py
```

Common options:

- Quiet pytest output (still runs behave):

```bash
python ./run_testing.py -q
```

- Skip behave (pytest only):

```bash
python ./run_testing.py --no-behave
```

- Behave only:

```bash
python ./run_testing.py --behave-only
```

### Run just a subset (pytest)

Examples:

```bash
python ./run_testing.py Testing/Articles -v
python ./run_testing.py Testing/User -v
python ./run_testing.py Testing/Sentiment/unit -v
```


# Authors

Connor Thiele - cthiele@email.sc.edu

Katie Jones - Katie.jones4@outlook.com

Sofia Bacha - sofbacha01@gmail.com

Kevin Do -  kdox1023@gmail.com

Andrew Lim - andrew.lim0023@gmail.com


