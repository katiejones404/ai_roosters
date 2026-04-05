"""
FastAPI application entry point for StockSense.

Notes
-----
Configures CORS, registers all API routers, runs database initialization on startup,
and launches background scheduler loops for alert checks, price ingestion, news
ingestion, and sentiment pipeline re-scoring.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text as sa_text

from app.api import auth, sentiment, portfolio, news, stocks, alerts as alerts_router, networth
from app.services.ingesting_pipelines.prices_ingest import PriceIngestor
from app.services.alert_scheduler import run_alert_checks
from app.db_init import init_db
import asyncio
import logging
import os
from datetime import date, datetime, timedelta, timezone

try:
    from app.services.sentiment.article_processing import run_finbert_pipeline_from_env
    from app.services.sentiment.stock_processing import run_returns_pipeline
    from app.services.sentiment.aggregator import run_sentiment_snapshot_pipeline_from_env
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

logger = logging.getLogger("startup")

TRUTHY_VALUES = {"1", "true", "yes", "on"}


def _env_bool(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in TRUTHY_VALUES


WEBSITE_TICKERS = [
    "KSS", "ALK", "NVS", "AXP", "FCX",
    "CSX", "DAL", "NTAP", "MRK", "COP",
    "BHP", "EA",
    "TSLA", "NVDA", "AAPL", "MSFT", "AMZN",
    "AMD", "META", "GOOGL", "GOOG", "PLTR",
    "MU", "NFLX",
    "NKE", "AAL", "BAC", "F", "INTC", "XOM", "T",
    "SOFI", "PLUG", "MARA", "SNAP", "COIN", "AMC", "RIVN", "CCL", "ENPH",
]

app = FastAPI(
    title="Stock Portfolio API",
    description="API for stock portfolio management with authentication",
    version="1.0.0"
)

FRONTEND_ORIGINS = os.getenv("FRONTEND_ORIGINS", "https://ai-roosters-webpage.vercel.app")
base_origins = [o.strip() for o in FRONTEND_ORIGINS.split(",") if o.strip()]

origins = base_origins + [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "https://sccapstone.github.io/ai_roosters/"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(sentiment.router, prefix="/api")
app.include_router(stocks.router, prefix="/api")
app.include_router(portfolio.router, prefix="/api")
app.include_router(news.router, prefix="/api")
app.include_router(alerts_router.router, prefix="/api/alerts")
app.include_router(networth.router, prefix="/api")
from app.stock_proxy import router as proxy_router   
app.include_router(proxy_router)                     


@app.on_event("startup")
def ingest_stock_prices_on_startup():
    """
    Run database initialization and optional data ingestion pipelines on startup.

    Notes
    -----
    Controlled by environment variables: RUN_ARTICLE_INGEST, RUN_PRICE_INGEST,
    RUN_ML_PIPELINES, INGEST_ALL_YEARS, and PRICE_INGEST_LOOKBACK_DAYS.
    Defaults are disabled for production-safe startups.
    Set to '1' to run.
    Also applies any pending schema migrations for columns added after initial deploy.
    """
    logger.info("Backend startup initiated...")

    run_article_ingest = _env_bool("RUN_ARTICLE_INGEST", "0")
    run_price_ingest = _env_bool("RUN_PRICE_INGEST", "0")
    run_ml_pipelines = _env_bool("RUN_ML_PIPELINES", "0")

    try:
        logger.info("Initializing database tables...")
        init_db()
        logger.info("Database initialization complete.")
    except Exception as e:
        logger.warning(f"Database initialization skipped or failed: {e}")
        logger.info("Tables may already exist, continuing...")

    # Ensure notification-related columns exist for alerts and users
    try:
        _mig_url = os.getenv("DATABASE_URL", "postgresql://stock_user:stock_pass@postgres:5432/stock_db")
        _mig_engine = create_engine(_mig_url)
        with _mig_engine.begin() as _conn:
            _conn.execute(sa_text(
                "ALTER TABLE price_alerts ADD COLUMN IF NOT EXISTS email_notify BOOLEAN NOT NULL DEFAULT TRUE"
            ))
            _conn.execute(sa_text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS notify_email_enabled BOOLEAN NOT NULL DEFAULT TRUE"
            ))
            _conn.execute(sa_text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS notify_market_alerts_enabled BOOLEAN NOT NULL DEFAULT TRUE"
            ))
            _conn.execute(sa_text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS notify_portfolio_updates_enabled BOOLEAN NOT NULL DEFAULT TRUE"
            ))
            _conn.execute(sa_text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS notify_weekly_report_enabled BOOLEAN NOT NULL DEFAULT FALSE"
            ))
            _conn.execute(sa_text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS notify_push_enabled BOOLEAN NOT NULL DEFAULT FALSE"
            ))
        _mig_engine.dispose()
        logger.info("Migration: notification columns ensured.")
    except Exception as e:
        logger.warning(f"Notification migrations skipped: {e}")

    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://stock_user:stock_pass@postgres:5432/stock_db"
    )

    try:
        if run_article_ingest:
            logger.info("RUN_ARTICLE_INGEST=1 — running article ingestion pipeline...")
            from app.services.ingesting_pipelines.news_ingest import run_hf_news_ingest_from_env
            run_hf_news_ingest_from_env(db_url=db_url)
            logger.info("Article ingestion complete.")
        else:
            logger.info("RUN_ARTICLE_INGEST != 1 — skipping article ingestion.")

        if run_price_ingest:
            logger.info("RUN_PRICE_INGEST=1 - ingesting price data...")
            ingestor = PriceIngestor(db_url)
            tickers = WEBSITE_TICKERS.copy()

            ingest_all_years = _env_bool("INGEST_ALL_YEARS", "0")
            try:
                lookback_days = max(int(os.getenv("PRICE_INGEST_LOOKBACK_DAYS", "30")), 1)
            except ValueError:
                lookback_days = 30

            logger.info(f"Price ingest tickers={tickers}")
            logger.info(
                "Price ingest config: ingest_all_years=%s lookback_days=%s",
                ingest_all_years,
                lookback_days,
            )

            if ingest_all_years:
                logger.info("Running full-history price backfill with period=max...")
                ingestor.ingest_multiple_stocks(
                    tickers=tickers,
                    start_date=None,
                    end_date=None,
                    period="max",
                    update_existing=False,
                    use_article_window_if_missing=False,
                )
            else:
                price_start = str(date.today() - timedelta(days=lookback_days))
                logger.info(f"Running incremental price ingest from {price_start} to {date.today()}.")
                ingestor.ingest_multiple_stocks(
                    tickers=tickers,
                    start_date=price_start,
                    end_date=str(date.today()),
                    period=None,
                    update_existing=True,
                    use_article_window_if_missing=False,
                )
            logger.info("Finished price ingestion.")
        else:
            logger.info("RUN_PRICE_INGEST != 1 - skipping price ingestion.")

        if run_ml_pipelines and ML_AVAILABLE:
            logger.info("RUN_ML_PIPELINES=1 — running ML pipelines...")

            logger.info("Running FinBERT pipeline...")
            run_finbert_pipeline_from_env()
            logger.info("FinBERT article processing complete.")

            logger.info("Running returns pipeline...")
            run_returns_pipeline()
            logger.info("Returns pipeline complete.")

            logger.info("Running sentiment snapshot pipeline...")
            run_sentiment_snapshot_pipeline_from_env()
            logger.info("Sentiment snapshot pipeline complete.")
        else:
            if not run_ml_pipelines:
                logger.info("RUN_ML_PIPELINES != 1 — skipping ML pipelines.")
            elif not ML_AVAILABLE:
                logger.info("ML pipeline libraries not installed — skipping FinBERT/sentiment pipelines.")

        logger.info("Backend startup complete.")

    except Exception as e:
        logger.error(f"Startup pipeline failed: {e}", exc_info=True)
        logger.warning("Backend will start anyway, but data pipelines did not complete.")


async def _alert_check_loop() -> None:
    """Run alert checks at a configurable interval."""
    try:
        initial_delay_seconds = int(os.getenv("ALERT_CHECK_INITIAL_DELAY_SECONDS", "30"))
    except ValueError:
        initial_delay_seconds = 30
    try:
        interval_seconds = int(os.getenv("ALERT_CHECK_INTERVAL_SECONDS", "300"))
    except ValueError:
        interval_seconds = 300
    interval_seconds = max(interval_seconds, 30)

    await asyncio.sleep(max(initial_delay_seconds, 0))
    while True:
        # Retry up to 5 times on connection errors (Neon cold-start) before
        # waiting the full interval. Retries use a short 15-second backoff.
        max_retries = 5
        for attempt in range(1, max_retries + 1):
            try:
                run_alert_checks()
                break  # success
            except Exception as e:
                err_str = str(e).lower()
                is_conn_err = any(kw in err_str for kw in ("connection refused", "could not connect", "operationalerror"))
                if is_conn_err and attempt < max_retries:
                    logger.warning(f"Alert check: DB connection failed (attempt {attempt}/{max_retries}), retrying in 15s...")
                    await asyncio.sleep(15)
                else:
                    logger.error(f"Alert check loop error: {e}", exc_info=True)
                    break
        await asyncio.sleep(interval_seconds)


async def _price_ingest_loop() -> None:
    """
    Ingest latest stock prices on weekdays during US market hours.

    Notes
    -----
    Only runs Monday through Friday between approximately 13:00 and 21:00 UTC,
    which covers 8 AM to 4 PM US Eastern in both EST and EDT.
    Interval is controlled by PRICE_INGEST_INTERVAL_SECONDS (default 900).
    """
    try:
        interval_seconds = int(os.getenv("PRICE_INGEST_INTERVAL_SECONDS", "900"))
    except ValueError:
        interval_seconds = 900
    interval_seconds = max(interval_seconds, 60)

    await asyncio.sleep(120)  # Allow startup to complete before first run
    while True:
        now_utc = datetime.now(timezone.utc)
        is_weekday = now_utc.weekday() < 5
        is_market_hours = 13 <= now_utc.hour < 21
        if is_weekday and is_market_hours:
            try:
                db_url = os.getenv("DATABASE_URL", "postgresql://stock_user:stock_pass@postgres:5432/stock_db")
                ingestor = PriceIngestor(db_url)
                ingestor.ingest_multiple_stocks(
                    tickers=WEBSITE_TICKERS,
                    start_date=str(date.today() - timedelta(days=5)),
                    end_date=str(date.today()),
                    period=None,
                    update_existing=True,
                )
                logger.info("Price ingest loop: ingestion complete.")
            except Exception as e:
                logger.error(f"Price ingest loop error: {e}", exc_info=True)
        await asyncio.sleep(interval_seconds)


async def _news_ingest_loop() -> None:
    """
    Ingest recent stock news articles from all configured sources on a recurring schedule.

    Notes
    -----
    Runs all four sources (Marketaux, NewsAPI, AlphaVantage, Guardian) in sequence.
    Sources with missing API keys are skipped without failing the others.
    Interval is controlled by NEWS_INGEST_INTERVAL_SECONDS (default 28800, i.e. 8 hours / 3x per day).
    """
    try:
        interval_seconds = int(os.getenv("NEWS_INGEST_INTERVAL_SECONDS", "28800"))
    except ValueError:
        interval_seconds = 28800
    interval_seconds = max(interval_seconds, 3600)

    await asyncio.sleep(180)  # Allow startup to complete before first run
    while True:
        any_ran = False

        if os.getenv("MARKETAUX_API_TOKEN", "").strip():
            try:
                from app.services.ingesting_pipelines.daily_news_ingest import run_daily_news_ingest_from_env
                run_daily_news_ingest_from_env()
                logger.info("News ingest loop: Marketaux complete.")
                any_ran = True
            except Exception as e:
                logger.error(f"News ingest loop (Marketaux) error: {e}", exc_info=True)
        else:
            logger.warning("News ingest loop: MARKETAUX_API_TOKEN not set, skipping.")

        if os.getenv("NEWSAPI_API_KEY", "").strip():
            try:
                from app.services.ingesting_pipelines.newsapi_ingest import run_newsapi_ingest_from_env
                run_newsapi_ingest_from_env()
                logger.info("News ingest loop: NewsAPI complete.")
                any_ran = True
            except Exception as e:
                logger.error(f"News ingest loop (NewsAPI) error: {e}", exc_info=True)
        else:
            logger.debug("News ingest loop: NEWSAPI_API_KEY not set, skipping.")

        if os.getenv("ALPHAVANTAGE_API_KEY", "").strip():
            try:
                from app.services.ingesting_pipelines.alphavantage_ingest import run_alphavantage_ingest_from_env
                run_alphavantage_ingest_from_env()
                logger.info("News ingest loop: AlphaVantage complete.")
                any_ran = True
            except Exception as e:
                logger.error(f"News ingest loop (AlphaVantage) error: {e}", exc_info=True)
        else:
            logger.debug("News ingest loop: ALPHAVANTAGE_API_KEY not set, skipping.")

        if os.getenv("GUARDIAN_API_KEY", "").strip():
            try:
                from app.services.ingesting_pipelines.guardian_ingest import run_guardian_ingest_from_env
                run_guardian_ingest_from_env()
                logger.info("News ingest loop: Guardian complete.")
                any_ran = True
            except Exception as e:
                logger.error(f"News ingest loop (Guardian) error: {e}", exc_info=True)
        else:
            logger.debug("News ingest loop: GUARDIAN_API_KEY not set, skipping.")

        if not any_ran:
            logger.warning("News ingest loop: no sources ran (all API keys missing).")

        await asyncio.sleep(interval_seconds)


async def _sentiment_pipeline_loop() -> None:
    """
    Re-run FinBERT scoring and sentiment aggregation on a recurring schedule.

    Notes
    -----
    Only executes when ML libraries are available (ML_AVAILABLE is True).
    Interval is controlled by SENTIMENT_INTERVAL_SECONDS (default 21600, i.e. 6 hours).
    """
    try:
        interval_seconds = int(os.getenv("SENTIMENT_INTERVAL_SECONDS", "21600"))
    except ValueError:
        interval_seconds = 21600
    interval_seconds = max(interval_seconds, 1800)

    if not ML_AVAILABLE:
        logger.info("Sentiment loop enabled but ML libraries are unavailable in this image.")

    await asyncio.sleep(300)  # Allow startup and news ingest to complete first
    while True:
        if ML_AVAILABLE:
            try:
                logger.info("Sentiment pipeline loop: starting re-scoring...")
                run_finbert_pipeline_from_env()
                run_returns_pipeline()
                run_sentiment_snapshot_pipeline_from_env()
                logger.info("Sentiment pipeline loop: complete.")
            except Exception as e:
                logger.error(f"Sentiment pipeline loop error: {e}", exc_info=True)
        await asyncio.sleep(interval_seconds)


@app.on_event("startup")
async def start_alert_scheduler() -> None:
    """
    Launch all background scheduler tasks on application startup.

    Notes
    -----
    Starts selected asyncio tasks for alert checks, price ingestion,
    news ingestion, and sentiment re-scoring. Use the environment variables
    ENABLE_BACKGROUND_SCHEDULERS, ENABLE_ALERT_SCHEDULER,
    ENABLE_PRICE_INGEST_SCHEDULER, ENABLE_NEWS_INGEST_SCHEDULER,
    and ENABLE_SENTIMENT_SCHEDULER to control behavior.
    """
    if not _env_bool("ENABLE_BACKGROUND_SCHEDULERS", "1"):
        logger.info("Background schedulers disabled via ENABLE_BACKGROUND_SCHEDULERS=0.")
        return

    started_tasks = []

    if _env_bool("ENABLE_ALERT_SCHEDULER", "1"):
        asyncio.create_task(_alert_check_loop())
        started_tasks.append("alerts")

    if _env_bool("ENABLE_PRICE_INGEST_SCHEDULER", "1"):
        asyncio.create_task(_price_ingest_loop())
        started_tasks.append("prices")

    if _env_bool("ENABLE_NEWS_INGEST_SCHEDULER", "1"):
        asyncio.create_task(_news_ingest_loop())
        started_tasks.append("news")

    if _env_bool("ENABLE_SENTIMENT_SCHEDULER", "1" if ML_AVAILABLE else "0"):
        asyncio.create_task(_sentiment_pipeline_loop())
        started_tasks.append("sentiment")

    if started_tasks:
        logger.info("Background scheduler tasks started: %s", ", ".join(started_tasks))
    else:
        logger.warning("Background schedulers are enabled, but no scheduler tasks were selected.")


@app.get("/")
def root():
    """
    Return a simple liveness response for the root path.

    Returns
    -------
    dict
        A message confirming the backend is running.
    """
    return {"message": "Backend is working!", "status": "healthy"}



@app.get("/health")
def health_check():
    """
    Return a health check response confirming the service is running.

    Returns
    -------
    dict
        Status and database connection indicator used by Azure health probes.
    """
    return {"status": "healthy", "database": "connected"}
