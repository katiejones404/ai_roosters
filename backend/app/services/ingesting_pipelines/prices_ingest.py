import os
import sys
import logging
from datetime import datetime
from typing import List, Optional

import yfinance as yf
import pandas as pd
from sqlalchemy import create_engine, MetaData, Table, text
from sqlalchemy.dialects.postgresql import insert

# Optional: if you need project root on path for other imports later
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger("price_ingestor")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s")
    )
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


def build_db_url() -> str:
    """
    Build DB URL from env vars.
    Used as a fallback if nothing is passed into PriceIngestor.
    """
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return db_url

    db_user = os.getenv("PG_USER", "stock_user")
    db_password = os.getenv("PG_PASS", "stock_pass")
    db_host = os.getenv("PG_HOST", "postgres")
    db_port = os.getenv("PG_PORT", "5432")
    db_name = os.getenv("PG_DB", "stock_db")

    return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"


class PriceIngestor:
    def __init__(self, db_url: Optional[str] = None):
        """
        Initialize the ingestor and reflect the 'stocks' table from the database.
        """
        if db_url is None:
            db_url = build_db_url()

        logger.info(f"Connecting to database at {db_url} ...")
        self.engine = create_engine(db_url)
        self.metadata = MetaData()

        # Reflect the existing 'stocks' table schema (including created_at, return_* etc.)
        logger.info("Reflecting 'stocks' table from database...")
        self.metadata.reflect(self.engine, only=["stocks"])
        if "stocks" not in self.metadata.tables:
            raise RuntimeError(
                "Table 'stocks' does not exist in the database. "
                "Make sure your SQL init scripts have created it."
            )

        self.stocks: Table = self.metadata.tables["stocks"]
        logger.info("Successfully reflected 'stocks' table.")

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------

    def fetch_stock_data(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: Optional[str] = "1y",
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data from yfinance for a single ticker.

        - If start_date & end_date are set, period is ignored.
        - Uses Close as adjusted_close for now.
        """
        try:
            logger.info(f"Fetching data for {ticker} ...")
            stock = yf.Ticker(ticker)

            if start_date and end_date:
                df = stock.history(start=start_date, end=end_date)
            else:
                df = stock.history(period=period or "1y")

            if df.empty:
                logger.warning(f"No data retrieved for {ticker}")
                return pd.DataFrame()

            df = df.reset_index()

            df = df.rename(
                columns={
                    "Date": "date",
                    "Open": "open",
                    "High": "high",
                    "Low": "low",
                    "Close": "close",
                    "Volume": "volume",
                }
            )

            df["adjusted_close"] = df["close"]
            df["ticker"] = ticker

            # Only the fields we want to insert here.
            # created_at is handled by DB default; returns handled by returns pipeline.
            columns = [
                "ticker",
                "date",
                "open",
                "high",
                "low",
                "close",
                "adjusted_close",
                "volume",
            ]
            df = df[columns]

            # Ensure 'date' is a Python date, not Timestamp
            df["date"] = pd.to_datetime(df["date"]).dt.date

            logger.info(f"Retrieved {len(df)} records for {ticker}")
            return df

        except Exception as e:
            logger.error(f"Error fetching data for {ticker}: {str(e)}")
            return pd.DataFrame()

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    def store_prices(self, df: pd.DataFrame, update_existing: bool = False) -> None:
        """
        Store price records in the stocks table.

        - If update_existing=True, upserts on (ticker, date).
        - If update_existing=False, ignores conflicts on (ticker, date).
        """
        if df.empty:
            logger.warning("No data to store (DataFrame is empty).")
            return

        try:
            records = df.to_dict("records")
            total_records = len(records)
            batch_size = 100
            records_processed = 0

            for i in range(0, total_records, batch_size):
                batch = records[i : i + batch_size]

                with self.engine.begin() as conn:
                    stmt = insert(self.stocks).values(batch)

                    if update_existing:
                        # Upsert on (ticker, date)
                        stmt = stmt.on_conflict_do_update(
                            index_elements=["ticker", "date"],
                            set_={
                                "open": stmt.excluded.open,
                                "high": stmt.excluded.high,
                                "low": stmt.excluded.low,
                                "close": stmt.excluded.close,
                                "adjusted_close": stmt.excluded.adjusted_close,
                                "volume": stmt.excluded.volume,
                            },
                        )
                    else:
                        # Ignore if row already exists
                        stmt = stmt.on_conflict_do_nothing(
                            index_elements=["ticker", "date"]
                        )

                    conn.execute(stmt)
                    records_processed += len(batch)
                    logger.info(f"Processed {records_processed}/{total_records} records")

            logger.info(f"Successfully stored {total_records} records into stocks table")

        except Exception as e:
            logger.error(f"Error storing prices: {str(e)}")
            raise

    # ------------------------------------------------------------------
    # Utilities & helpers
    # ------------------------------------------------------------------

    def ingest_multiple_stocks(
        self,
        tickers: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: Optional[str] = "1y",
        update_existing: bool = False,
    ) -> None:
        """
        Fetch and store prices for multiple tickers.
        """
        for ticker in tickers:
            logger.info(f"Processing {ticker} ...")
            df = self.fetch_stock_data(
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
                period=period,
            )
            if not df.empty:
                self.store_prices(df, update_existing=update_existing)
            else:
                logger.warning(f"Skipping {ticker} - no data retrieved")

    def get_latest_date(self, ticker: str) -> Optional[datetime]:
        """
        Return the most recent date stored for a given ticker.
        """
        try:
            with self.engine.connect() as conn:
                query = text(
                    """
                    SELECT MAX(date) AS latest_date
                    FROM stocks
                    WHERE ticker = :ticker
                    """
                )
                result = conn.execute(query, {"ticker": ticker}).fetchone()
                return result[0] if result and result[0] else None
        except Exception as e:
            logger.error(f"Error getting latest date for {ticker}: {str(e)}")
            return None

    def backfill_missing_data(self, ticker: str, target_start_date: str) -> None:
        """
        Example helper: backfill from target_start_date up to latest existing date (or now).
        """
        latest = self.get_latest_date(ticker)

        if latest:
            logger.info(f"Latest existing data for {ticker}: {latest}")
            df = self.fetch_stock_data(
                ticker=ticker,
                start_date=target_start_date,
                end_date=str(latest),
            )
        else:
            logger.info(
                f"No existing data for {ticker}, fetching from {target_start_date} onward"
            )
            df = self.fetch_stock_data(ticker=ticker, start_date=target_start_date)

        if not df.empty:
            self.store_prices(df, update_existing=False)
        else:
            logger.warning(f"No data fetched for backfill of {ticker}")

# to rerun the stock ingestion use this command
# docker compose exec api python -m app.services.ingesting_pipelines.prices_ingest
if __name__ == "__main__":
    # Optional CLI usage, doesn't affect FastAPI integration
    ingestor = PriceIngestor()
    stocks = ["KSS","ALK", "NVS", "AXP", "FCX", "CSX", "DAL", "NTAP", "GPS", "AEO",
              "MRK", "DFS", "COP", "BHP", "EA"]
    
    with ingestor.engine.begin() as conn:
        conn.execute(
            text("DELETE FROM stocks WHERE ticker != ALL(:tickers)"),
            {"tickers": stocks}
        )
        logger.info("Removed old tickers from database.")
        
    ingestor.ingest_multiple_stocks(
        tickers=stocks,
        start_date= None,
        end_date= None,
        period="5y",
        update_existing=True,
    )
    logger.info("Manual price ingestion complete.")
