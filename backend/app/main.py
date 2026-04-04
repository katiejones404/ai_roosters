from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text as sa_text

from app.api import auth, sentiment, portfolio, news, stocks, alerts as alerts_router, networth
from app.services.ingesting_pipelines.prices_ingest import PriceIngestor
from app.services.alerts_logic import is_alert_triggered, should_send_alert_email
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


@app.on_event("startup")
def ingest_stock_prices_on_startup():
    logger.info("Backend startup initiated...")

    run_article_ingest = os.getenv("RUN_ARTICLE_INGEST", "0") == "1"
    run_price_ingest = os.getenv("RUN_PRICE_INGEST", "1") == "1"
    run_ml_pipelines = os.getenv("RUN_ML_PIPELINES", "1") == "1"

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
            from app.services.ingesting_pipelines.news_ingest import ArticleIngestor
            ArticleIngestor(db_url).ingest_all_years_one_pass(
                years=list(range(2020, date.today().year + 1)),
                per_year=1000,
                end_date=date.today().isoformat(),
                max_scanned=50_000_000,
                flush_batch_size=2000,
                streaming=True,
            )
            logger.info("Article ingestion complete.")
        else:
            logger.info("RUN_ARTICLE_INGEST != 1 — skipping article ingestion.")

        if run_price_ingest:
            logger.info("RUN_PRICE_INGEST=1 — ingesting price data...")
            ingestor = PriceIngestor(db_url)
            tickers = WEBSITE_TICKERS.copy()

            _engine = create_engine(db_url)
            cutoff = date.today() - timedelta(days=1000)
            with _engine.connect() as _conn:
                _count = _conn.execute(
                    sa_text("SELECT COUNT(*) FROM stocks WHERE date < :d AND ticker = ANY(:tickers)"),
                    {"d": str(cutoff), "tickers": tickers}
                ).scalar()
            _engine.dispose()
            has_history = (_count or 0) > 0
            price_start = str(date.today() - timedelta(days=30)) if has_history else "2020-01-01"
            logger.info(f"Price ingest tickers={tickers}")
            logger.info(f"Price ingest start_date={price_start} (has_history={has_history})")

            ingestor.ingest_multiple_stocks(
                tickers=tickers,
                start_date=price_start,
                end_date=str(date.today()),
                period=None,
                update_existing=False,
            )
            logger.info("Finished price ingestion.")
        else:
            logger.info("RUN_PRICE_INGEST != 1 — skipping price ingestion.")

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


def run_alert_checks() -> None:
    """Check all active price alerts against latest stock prices and email on trigger."""
    from sqlalchemy import create_engine, text as _text
    from sqlalchemy.orm import sessionmaker
    from app.models.models import PriceAlert
    from app.services.email_service import send_price_alert_email


    db_url = os.getenv("DATABASE_URL", "postgresql://stock_user:stock_pass@postgres:5432/stock_db")
    _engine = create_engine(db_url)
    Session = sessionmaker(bind=_engine)
    db = Session()
    try:

        alerts = db.query(PriceAlert).filter(PriceAlert.is_active == True).all()  # noqa: E712
        if not alerts:
            return
        tickers = list({a.ticker for a in alerts})
        rows = db.execute(
            _text(
                "SELECT DISTINCT ON (ticker) ticker, close FROM stocks "
                "WHERE ticker = ANY(:tickers) AND close IS NOT NULL "
                "ORDER BY ticker, date DESC"
            ),
            {"tickers": tickers},
        ).fetchall()
        latest_prices = {row[0]: float(row[1]) for row in rows}

        for alert in alerts:

            current = latest_prices.get(alert.ticker)
            if current is None:
                continue
            if not alert.user:
                continue
            target = float(alert.target_price)
            triggered = is_alert_triggered(alert.direction, current, target)
            if triggered:

                user_email_enabled = bool(
                    True
                    if alert.user.notify_email_enabled is None
                    else alert.user.notify_email_enabled
                )
                user_market_alerts_enabled = bool(
                    True
                    if alert.user.notify_market_alerts_enabled is None
                    else alert.user.notify_market_alerts_enabled
                )

                if should_send_alert_email(
                    alert.email_notify,
                    user_email_enabled,
                    user_market_alerts_enabled,
                ):
                    try:
                        send_price_alert_email(
                            to_email=alert.user.email,
                            ticker=alert.ticker,
                            direction=alert.direction,
                            target_price=target,
                            current_price=current,
                        )
                        logger.info(f"Alert email sent: {alert.ticker} {alert.direction} {target}")
                    except Exception as email_err:
                        logger.warning(f"Alert email failed for {alert.ticker}: {email_err}")
                else:
                    logger.info(
                        "Alert triggered (email disabled by alert/user preferences): "
                        f"{alert.ticker} {alert.direction} {target}"
                    )
                alert.is_active = False
                alert.triggered_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:
        logger.error(f"Alert check failed: {e}", exc_info=True)
    finally:

        db.close()
        _engine.dispose()


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
        try:
            run_alert_checks()
        except Exception as e:
            logger.error(f"Alert check loop error: {e}", exc_info=True)
        await asyncio.sleep(interval_seconds)




@app.on_event("startup")

async def start_alert_scheduler() -> None:
    asyncio.create_task(_alert_check_loop())
    logger.info("Price alert scheduler started.")


@app.get("/")
def root():
    return {"message": "Backend is working!", "status": "healthy"}



@app.get("/health")
def health_check():
    return {"status": "healthy", "database": "connected"}
