from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, sentiment, news, stocks
from app.services.prices_ingest import PriceIngestor
from app.services.sentiment.article_processing import run_finbert_pipeline_from_env
from app.services.sentiment.stock_processing import run_returns_pipeline
from app.services.sentiment.aggregator import run_sentiment_snapshot_pipeline_from_env
from app.db_init import init_db  
import logging
import os

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

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins = origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api")
app.include_router(sentiment.router)
app.include_router(stocks.router)

# Automates price ingestion on startup 
@app.on_event("startup")
def ingest_stock_prices_on_startup():
    logger.info("Backend startup initiated...")
    
    # Initialize database tables first
    try:
        logger.info("Initializing database tables...")
        init_db()
        logger.info("Database initialization complete.")
    except Exception as e:
        logger.warning(f"Database initialization skipped or failed: {e}")
        logger.info("Tables may already exist, continuing...")
    
    # Database URL
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://stock_user:stock_pass@postgres:5432/stock_db"
    )
    
    try:
        # 1. Ingest prices
        logger.info(f"Ingesting price data...")
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
        
        # 2. FinBERT article sentiment
        logger.info("Running FinBERT pipeline...")
        run_finbert_pipeline_from_env()
        logger.info("FinBERT article processing complete.")
        
        # 3. Calculate returns
        logger.info("Running returns pipeline...")
        run_returns_pipeline()
        logger.info("Returns pipeline complete.")
        
        # 4. Aggregate sentiment snapshots
        logger.info("Running sentiment snapshot pipeline...")
        run_sentiment_snapshot_pipeline_from_env()
        logger.info("Sentiment snapshot pipeline complete.")
        
        logger.info("Backend startup complete, all pipelines finished.")
        
    except Exception as e:
        logger.error(f"Startup pipeline failed: {e}", exc_info=True)
        logger.warning("Backend will start anyway, but data pipelines did not complete.")


@app.get("/")
def root():
    return {"message": "Backend is working!", "status": "healthy"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "database": "connected"}