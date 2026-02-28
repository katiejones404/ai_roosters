import os
import sys
import logging
from datetime import datetime, date, timedelta
from typing import List, Optional, Tuple

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
        if db_url is None:
            db_url = build_db_url()

        logger.info(f"Connecting to database at {db_url} ...")
        self.engine = create_engine(db_url)
        self.metadata = MetaData()

        logger.info("Reflecting 'stocks' table from database...")
        self.metadata.reflect(self.engine, only=["stocks"])
        if "stocks" not in self.metadata.tables:
            raise RuntimeError(
                "Table 'stocks' does not exist in the database. "
                "Make sure your SQL init scripts have created it."
            )

        self.stocks: Table = self.metadata.tables["stocks"]
        logger.info("Successfully reflected 'stocks' table.")

    # ------------------------------------------------------------
    # Article date window helpers
    # ------------------------------------------------------------

    def get_article_date_range(self) -> Tuple[date, date]:
        """
        Returns (min_date, max_date) from articles.published_at as *dates*.
        """
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT MIN(published_at), MAX(published_at) FROM articles;")
            ).fetchone()

        if not row or row[0] is None or row[1] is None:
            raise RuntimeError(
                "Could not determine article date range. "
                "Make sure 'articles' has published_at populated."
            )

        min_dt: datetime = row[0]
        max_dt: datetime = row[1]
        return min_dt.date(), max_dt.date()

    def normalize_price_window(
        self,
        start_date: Optional[str],
        end_date: Optional[str],
        use_article_window_if_missing: bool = True,
    ) -> Tuple[str, str]:
        """
        Ensures we always have a bounded [start, end] window aligned to articles.
        Returns ISO date strings (YYYY-MM-DD).

        Note: yfinance's `end` is effectively exclusive, so we will add +1 day
        at fetch-time (see fetch_stock_data).
        """
        if start_date and end_date:
            return start_date, end_date

        if not use_article_window_if_missing:
            # fallback to a sensible default
            today = date.today()
            return str(today - timedelta(days=365)), str(today)

        min_d, max_d = self.get_article_date_range()
        return str(min_d), str(max_d)

    # ------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------

    def fetch_stock_data(
        self,
        ticker: str,
        start_date: Optional[str] = None,   # YYYY-MM-DD
        end_date: Optional[str] = None,     # YYYY-MM-DD (inclusive intent)
        period: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data from yfinance.

        - If start_date & end_date are set: uses them.
        - `end_date` is treated as inclusive by adding +1 day (yfinance end is exclusive-ish).
        - Uses Close as adjusted_close for now.
        """
        try:
            logger.info(f"Fetching data for {ticker} ...")
            stock = yf.Ticker(ticker)

            if start_date and end_date:
                # make end inclusive
                end_plus_one = (pd.to_datetime(end_date) + pd.Timedelta(days=1)).date()
                df = stock.history(start=start_date, end=str(end_plus_one))
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

            # If the caller provided an intended window, hard-filter to it
            if start_date and end_date:
                s = pd.to_datetime(start_date).date()
                e = pd.to_datetime(end_date).date()
                df = df[(df["date"] >= s) & (df["date"] <= e)]

            logger.info(f"Retrieved {len(df)} records for {ticker}")
            return df

        except Exception as e:
            logger.error(f"Error fetching data for {ticker}: {str(e)}")
            return pd.DataFrame()

    # ------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------

    def store_prices(self, df: pd.DataFrame, update_existing: bool = False) -> None:
        if df.empty:
            logger.warning("No data to store (DataFrame is empty).")
            return

        try:
            records = df.to_dict("records")
            total_records = len(records)
            batch_size = 500  # a bit bigger is fine
            records_processed = 0

            for i in range(0, total_records, batch_size):
                batch = records[i : i + batch_size]

                with self.engine.begin() as conn:
                    stmt = insert(self.stocks).values(batch)

                    if update_existing:
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
                        stmt = stmt.on_conflict_do_nothing(index_elements=["ticker", "date"])

                    conn.execute(stmt)

                records_processed += len(batch)
                logger.info(f"Processed {records_processed}/{total_records} records")

            logger.info(f"Successfully stored {total_records} records into stocks table")

        except Exception as e:
            logger.error(f"Error storing prices: {str(e)}")
            raise

    # ------------------------------------------------------------
    # Main ingest
    # ------------------------------------------------------------

    def ingest_multiple_stocks(
        self,
        tickers: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: Optional[str] = None,
        update_existing: bool = False,
        use_article_window_if_missing: bool = True,
    ) -> None:
        """
        Fetch and store prices for multiple tickers.

        If start/end not provided, defaults to articles' min/max published_at dates.
        """
        start_date, end_date = self.normalize_price_window(
            start_date=start_date,
            end_date=end_date,
            use_article_window_if_missing=use_article_window_if_missing,
        )

        logger.info(f"Price ingest window: {start_date} -> {end_date} (inclusive)")

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


# to rerun the stock ingestion use this command
# docker compose exec api python -m app.services.ingesting_pipelines.prices_ingest
if __name__ == "__main__":
    ingestor = PriceIngestor()
    stocks = [
        "AAPL", "TSLA", "MSFT", "GOOGL", "AMZN",
        "META", "NVDA", "JPM", "BP", "RELIANCE.NS",
        "KSS", "ALK", "NVS", "AXP",
    ]

    ''' 
    Original stocks before additions/deletions:
        "KSS","ALK", "NVS", "AXP", "FCX", "CSX", "DAL", "NTAP", "AMZN", "AEO",
        "MRK", "NVDA", "COP", "BHP", "EA"
        '''
    # Remove old tickers safely
    with ingestor.engine.begin() as conn:
        conn.execute(
            text("DELETE FROM stocks WHERE NOT (ticker = ANY(:tickers));"),
            {"tickers": stocks},
        )
        logger.info("Removed old tickers from database (kept only current tickers).")

    ingestor.ingest_multiple_stocks(
        tickers=stocks,
        start_date="2020-01-01",
        end_date=str(date.today()),
        period=None,
        update_existing=True,
    )

    logger.info("Manual price ingestion complete.")