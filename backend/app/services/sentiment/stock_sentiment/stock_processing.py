import os
import logging
from typing import Optional, List

import pandas as pd
from sqlalchemy import create_engine, text

logger = logging.getLogger("returns_pipeline")
logger.setLevel(logging.INFO)
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(_handler)


def get_db_url() -> str:
    """Build DB URL from env vars (same pattern as your PriceIngestor)."""
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return db_url

    db_user = os.getenv("PG_USER", "stock_user")
    db_password = os.getenv("PG_PASS", "stock_pass")
    db_host = os.getenv("PG_HOST", "postgres")
    db_port = os.getenv("PG_PORT", "5432")
    db_name = os.getenv("PG_DB", "stock_db")

    return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"


def ensure_return_columns(engine) -> None:
    """
    Add return columns to stocks table if they don't exist.
    Safe to run multiple times.
    """
    logger.info("Ensuring return columns exist on stocks table...")
    alter_sql = """
        ALTER TABLE stocks
        ADD COLUMN IF NOT EXISTS return_1d   NUMERIC,
        ADD COLUMN IF NOT EXISTS return_30d  NUMERIC,
        ADD COLUMN IF NOT EXISTS return_120d NUMERIC,
        ADD COLUMN IF NOT EXISTS return_360d NUMERIC;
    """
    with engine.begin() as conn:
        conn.execute(text(alter_sql))
    logger.info("Return columns verified/added.")


def load_prices(engine, tickers: Optional[List[str]] = None) -> pd.DataFrame:
    """
    Load price data from stocks.
    """
    base_query = """
        SELECT
            ticker,
            date,
            adjusted_close
        FROM stocks
    """

    params = {}
    if tickers:
        base_query += " WHERE ticker = ANY(:tickers)"
        params["tickers"] = tickers

    base_query += " ORDER BY ticker, date"

    logger.info("Loading price data from database...")
    df = pd.read_sql(text(base_query), engine, params=params, parse_dates=["date"])
    logger.info(f"Loaded {len(df)} rows from stocks table")
    return df


def add_returns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute 1d, 30d, 120d, 360d returns per ticker using adjusted_close.
    Returns are decimals (0.05 = 5%).
    """
    if df.empty:
        logger.warning("Empty DataFrame passed to add_returns()")
        return df

    df = df.copy().sort_values(["ticker", "date"])
    grouped = df.groupby("ticker", group_keys=False)

    df["return_1d"] = grouped["adjusted_close"].pct_change(periods=1)
    df["return_30d"] = grouped["adjusted_close"].pct_change(periods=30)
    df["return_120d"] = grouped["adjusted_close"].pct_change(periods=120)
    df["return_360d"] = grouped["adjusted_close"].pct_change(periods=360)

    logger.info("Computed 1d, 30d, 120d, 360d returns")
    return df


def update_returns_in_db(engine, df: pd.DataFrame) -> None:
    """
    Update stocks table with computed returns.
    Matches rows on (ticker, date).
    """
    if df.empty:
        logger.warning("No data to update in DB.")
        return

    # Replace NaN with None so Postgres sees NULL
    for col in ["return_1d", "return_30d", "return_120d", "return_360d"]:
        df[col] = df[col].where(pd.notnull(df[col]), None)

    rows = df[
        ["ticker", "date", "return_1d", "return_30d", "return_120d", "return_360d"]
    ].to_dict("records")

    logger.info(f"Updating {len(rows)} rows with returns...")
    update_sql = text(
        """
        UPDATE stocks
        SET
            return_1d   = :return_1d,
            return_30d  = :return_30d,
            return_120d = :return_120d,
            return_360d = :return_360d
        WHERE ticker = :ticker AND date = :date
    """
    )

    with engine.begin() as conn:
        conn.execute(update_sql, rows)

    logger.info("Database update complete.")


def main():
    db_url = get_db_url()
    logger.info(f"Connecting to database at {db_url} ...")
    engine = create_engine(db_url)

    # 1. Ensure columns exist
    ensure_return_columns(engine)

    # 2. Load prices (all tickers, or specify list)
    tickers = None  # e.g. ["BP", "RELIANCE.NS"]
    df = load_prices(engine, tickers=tickers)

    # 3. Compute returns
    df_with_returns = add_returns(df)

    # 4. Update DB
    update_returns_in_db(engine, df_with_returns)

    # Optional: peek at first few rows
    logger.info("Sample rows with returns:")
    print(df_with_returns.head(10).to_string(index=False, justify="left"))


if __name__ == "__main__":
    main()
