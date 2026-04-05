import os
import logging
from typing import Optional, List

import pandas as pd
from sqlalchemy import create_engine, text

logger = logging.getLogger("returns_pipeline")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)

DEFAULT_RETURNS_START_DATE = "2020-01-01"


def get_db_url() -> str:
    """Build DB URL from env vars (same pattern as PriceIngestor)."""
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return db_url

    db_user = os.getenv("PG_USER", "stock_user")
    db_password = os.getenv("PG_PASS", "stock_pass")
    db_host = os.getenv("PG_HOST", "postgres")
    db_port = os.getenv("PG_PORT", "5432")
    db_name = os.getenv("PG_DB", "stock_db")

    return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"


def get_returns_start_date() -> pd.Timestamp:
    raw = (os.getenv("RETURNS_START_DATE", DEFAULT_RETURNS_START_DATE) or "").strip()
    if not raw:
        raw = DEFAULT_RETURNS_START_DATE
    try:
        return pd.Timestamp(raw).normalize()
    except Exception:
        logger.warning(
            "Invalid RETURNS_START_DATE=%r; falling back to %s",
            raw,
            DEFAULT_RETURNS_START_DATE,
        )
        return pd.Timestamp(DEFAULT_RETURNS_START_DATE).normalize()


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
            adjusted_close,
            return_1d AS existing_return_1d,
            return_30d AS existing_return_30d,
            return_120d AS existing_return_120d,
            return_360d AS existing_return_360d
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

    returns_start = get_returns_start_date()
    date_series = pd.to_datetime(df["date"]).dt.normalize()
    pre_cutoff_mask = date_series < returns_start
    if pre_cutoff_mask.any():
        df.loc[pre_cutoff_mask, ["return_1d", "return_30d", "return_120d", "return_360d"]] = pd.NA

    logger.info("Computed 1d, 30d, 120d, 360d returns")
    return df


def update_returns_in_db(
    engine,
    df: pd.DataFrame,
    batch_size: int = 500,
    only_missing: bool = True,
) -> None:
    """
    Update stocks table with computed returns.
    Matches rows on (ticker, date).

    Commits in batches of batch_size to avoid Neon connection timeouts
    that occur when sending all 23k rows in a single executemany call.
    """
    if df.empty:
        logger.warning("No data to update in DB.")
        return

    return_cols = ["return_1d", "return_30d", "return_120d", "return_360d"]
    existing_cols = [f"existing_{c}" for c in return_cols]
    returns_start = get_returns_start_date()
    date_series = pd.to_datetime(df["date"]).dt.normalize()
    pre_cutoff_mask = date_series < returns_start

    # In "only_missing" mode, only update rows where at least one return
    # value is currently NULL in DB and now computable.
    if only_missing and all(c in df.columns for c in existing_cols):
        missing_then_computable = pd.Series(False, index=df.index)
        for c in return_cols:
            existing_col = f"existing_{c}"
            missing_then_computable = missing_then_computable | (
                df[existing_col].isna() & df[c].notna()
            )

        pre_cutoff_needs_clear = pre_cutoff_mask & df[existing_cols].notna().any(axis=1)
        rows_to_update = missing_then_computable | pre_cutoff_needs_clear

        before_count = len(df)
        df = df.loc[rows_to_update].copy()
        logger.info(
            "Only-missing mode enabled: %s/%s rows require return updates.",
            len(df),
            before_count,
        )

    # Replace NaN with None so Postgres sees NULL/None in params.
    for col in return_cols:
        df[col] = df[col].where(pd.notnull(df[col]), None)

    rows = df[["ticker", "date"] + return_cols].to_dict("records")

    total = len(rows)
    if total == 0:
        logger.info("No return rows need updating.")
        return
    logger.info(f"Updating {total} rows with returns (batch_size={batch_size})...")
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

    # Send rows in small batches so Neon doesn't drop the connection
    for start in range(0, total, batch_size):
        batch = rows[start : start + batch_size]
        with engine.begin() as conn:
            conn.execute(update_sql, batch)
        logger.info(f"Committed rows {start + len(batch)}/{total}")

    logger.info("Database update complete.")


def run_returns_pipeline(
    tickers: Optional[List[str]] = None,
    only_missing: bool = True,
    batch_size: int = 500,
) -> None:
    """
    Public entry point: compute & update returns for all tickers (or a subset).
    This is what we'll call from FastAPI startup.
    """
    db_url = get_db_url()
    logger.info(f"Connecting to database at {db_url} ...")
    engine = create_engine(db_url)

    # 1. Ensure columns exist
    ensure_return_columns(engine)

    # 2. Load prices
    df = load_prices(engine, tickers=tickers)

    # 3. Compute returns
    df_with_returns = add_returns(df)

    # 4. Update DB
    update_returns_in_db(
        engine,
        df_with_returns,
        batch_size=batch_size,
        only_missing=only_missing,
    )

    # Optional: peek at first few rows
    logger.info("Sample rows with returns:")
    if not df_with_returns.empty:
        print(df_with_returns.head(10).to_string(index=False, justify="left"))
    else:
        logger.info("No rows to show - df_with_returns is empty.")


if __name__ == "__main__":
    # CLI usage: python app/services/returns_pipeline.py
    only_missing = os.getenv("RETURNS_ONLY_MISSING", "1").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    batch_size = int(os.getenv("RETURNS_BATCH_SIZE", "500"))
    run_returns_pipeline(only_missing=only_missing, batch_size=batch_size)
