from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, sentiment, news, stocks
from app.services.prices_ingest import PriceIngestor
from app.services.sentiment.article_sentiment.article_processing import run_finbert_pipeline_from_env
from app.services.sentiment.stock_sentiment.stock_processing import run_returns_pipeline
from app.services.sentiment.aggregator import run_sentiment_snapshot_pipeline_from_env
import logging
import os

logger = logging.getLogger("startup")

app = FastAPI(
    title="Stock Portfolio API",
    description="API for stock portfolio management with authentication",
    version="1.0.0"
)

FRONTEND_ORIGINS = os.getenv("FRONTEND_ORIGINS", "https://ai-roosters-pofj.vercel.app")

# FRONTEND_ORIGINS may be a comma-separated list
base_origins = [o.strip() for o in FRONTEND_ORIGINS.split(",") if o.strip()]

origins = base_origins + [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
]
# Configure CORS
app.add_middleware(
    CORSMiddleware,
    #allow_origins=["http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:5173", "http://localhost:3000"],
    #allow_origins=["*"], #Safe for now, not safe for production
    allow_origins = origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include auth router ← ADD THIS LINE
app.include_router(auth.router, prefix="/api")
app.include_router(sentiment.router)
app.include_router(stocks.router)

# Automates price ingestion on startup 
@app.on_event("startup")
def ingest_stock_prices_on_startup():
    logger.info(" Backend startup initiated...")
    # 1. Ingest prices
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://stock_user:stock_pass@postgres:5432/stock_db"
    )
    ingestor = PriceIngestor(db_url)
    tickers = ["BP", "RELIANCE.NS"]
    logger.info(f"Ingesting price data for {tickers} ...")
    ingestor.ingest_multiple_stocks(
        tickers=tickers,
        start_date="2021-10-01",
        end_date="2022-02-28",
        period=None,
        update_existing=False,
    )
    logger.info("Finished price ingestion.")
    # 2. FinBERT article sentiment
    logger.info("Running FinBERT pipeline...")
    run_finbert_pipeline_from_env()
    logger.info("FinBERT article processing complete.")
    # 3.Calculate returns
    logger.info("Running returns pipeline...")
    run_returns_pipeline()
    logger.info("Returns pipeline complete.")
    # 4. Aggregate sentiment snapshots
    logger.info("Running sentiment snapshot pipeline...")
    run_sentiment_snapshot_pipeline_from_env()
    logger.info("Sentiment snapshot pipeline complete.")
    logger.info("Backend startup complete, all loaders finished.")



@app.get("/")
def root():

    return {"message": "Backend is working!", "status": "healthy"}

@app.get("/health")
def health_check():

    return {"status": "healthy", "database": "connected"}