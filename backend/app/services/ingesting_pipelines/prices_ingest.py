from __future__ import annotations

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


def dedupe_keep_order(values: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for v in values:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


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

    def resolve_target_tickers(self) -> List[str]:
        raw = (os.getenv("PRICE_TICKERS") or "").strip()
        if raw:
            tickers = [x.strip().upper() for x in raw.split(",") if x.strip()]
            tickers = dedupe_keep_order(tickers)
            logger.info(f"Using PRICE_TICKERS override with {len(tickers)} ticker(s).")
            return tickers

        logger.info(f"Using default website ticker universe with {len(WEBSITE_TICKERS)} ticker(s).")
        return WEBSITE_TICKERS.copy()

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

        if start_date and not end_date:
            return start_date, str(date.today())

        if end_date and not start_date:
            end_dt = pd.to_datetime(end_date).date()
            return str(end_dt - timedelta(days=365)), end_date

        if not use_article_window_if_missing:
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
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
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
            df["date"] = pd.to_datetime(df["date"]).dt.date

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
            batch_size = 500
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
        if period and not start_date and not end_date:
            logger.info(f"Price ingest using period={period}")
        else:
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


if __name__ == "__main__":
    ingestor = PriceIngestor()
    tickers = ingestor.resolve_target_tickers()

    start_date = (os.getenv("PRICE_START_DATE") or "").strip() or None
    end_date = (os.getenv("PRICE_END_DATE") or "").strip() or None
    period = (os.getenv("PRICE_PERIOD") or "").strip() or None
    if not start_date and not end_date and not period:
        # Default manual mode to full listing history.
        period = "max"
    update_existing = (os.getenv("PRICE_UPDATE_EXISTING", "1").strip().lower() in {"1", "true", "yes", "on"})

    ingestor.ingest_multiple_stocks(
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        period=period,
        update_existing=update_existing,
        use_article_window_if_missing=False,
    )

    logger.info("Manual price ingestion complete.")
