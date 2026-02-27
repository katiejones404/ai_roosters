from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, sentiment, portfolio, news, stocks
from app.services.ingesting_pipelines.prices_ingest import PriceIngestor
from app.db_init import init_db
import logging
import os

# ML pipeline imports — only available in the pipeline container (not the slim API container)
try:
    from app.services.sentiment.article_processing import run_finbert_pipeline_from_env
    from app.services.sentiment.stock_processing import run_returns_pipeline
    from app.services.sentiment.aggregator import run_sentiment_snapshot_pipeline_from_env
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

logger = logging.getLogger("startup")

app = FastAPI(
    title="Stock Portfolio API",
    description="API for stock portfolio management with authentication",
    version="1.0.0"
)

FRONTEND_ORIGINS = os.getenv("FRONTEND_ORIGINS", "https://ai-roosters-frontend.onrender.com")
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

# Include routers
app.include_router(auth.router, prefix="/api")
app.include_router(sentiment.router, prefix="/api")
app.include_router(stocks.router, prefix="/api")
app.include_router(portfolio.router, prefix="/api")
# app.include_router(news.router, prefix="/api")

@app.on_event("startup")
def ingest_stock_prices_on_startup():
    logger.info("Backend startup initiated...")

    # Feature flags
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

    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://stock_user:stock_pass@postgres:5432/stock_db"
    )

    try:
        # 1) (Optional) Article ingestion (HF -> Postgres)
        # Guarded to avoid doing this on every boot.
        if run_article_ingest:
            logger.info("RUN_ARTICLE_INGEST=1 — running article ingestion pipeline...")

            from app.services.ingesting_pipelines.article_ingest import ArticleIngestor

            top15 = [
                "KSS", "ALK", "NVS", "AXP", "FCX",
                "CSX", "DAL", "NTAP", "GPS", "AEO",
                "MRK", "DFS", "COP", "BHP", "EA",
            ]

            ArticleIngestor(db_url).ingest_equal_by_year(
                tickers=top15,
                start_date="2010-01-01",
                end_date="2024-12-01",
                total_per_ticker=5000,   # 5k TOTAL per stock across the whole range
                batch_size=250,
            )

            logger.info("Article ingestion complete.")
        else:
            logger.info("RUN_ARTICLE_INGEST != 1 — skipping article ingestion.")

        # 2) (Optional) Price ingestion
        if run_price_ingest:
            logger.info("RUN_PRICE_INGEST=1 — ingesting price data...")
            ingestor = PriceIngestor(db_url)
            tickers = ["BP", "RELIANCE.NS"]
            ingestor.ingest_multiple_stocks(
                tickers=tickers,
                start_date="2021-10-01",
                end_date="2022-02-28",
                period=None,
                update_existing=False,
            )
            logger.info("Finished price ingestion.")
        else:
            logger.info("RUN_PRICE_INGEST != 1 — skipping price ingestion.")

        # 3) (Optional) ML pipelines
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

@app.get("/")
def root():
    return {"message": "Backend is working!", "status": "healthy"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "database": "connected"}