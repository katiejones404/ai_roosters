"""
alphavantage_ingest.py

Ingests financial news articles from the AlphaVantage NEWS_SENTIMENT endpoint
for each of the 15 target tickers and writes them into stock_news_articles.

AlphaVantage is uniquely suited to this project because the API filters news
by ticker symbol natively, so every article returned is relevant to the stock.
The response also includes relevance scores and pre-computed sentiment, though
We run FinBERT over all articles afterward so we store the raw text, not AV sentiment.

Free tier limits:
    - 25 requests per day total
    - 5 requests per minute
    - Up to 1000 articles per request (set limit=500 to stay conservative)
    - Approximately 2 years of historical data available

With 15 tickers and 1 request each, this uses 15 of the 25 daily requests.
A 12-second delay between tickers keeps the rate safely under 5/min.

Usage:
    docker compose --profile pipeline run --rm pipeline \
        python -m app.services.ingesting_pipelines.alphavantage_ingest

Environment variables:
    ALPHAVANTAGE_API_KEY      -- (required) AlphaVantage API key
    ALPHAVANTAGE_LOOKBACK_DAYS -- days back to fetch (default: 7)
    ALPHAVANTAGE_LIMIT        -- articles per ticker per call (default: 200)
    ALPHAVANTAGE_DELAY_SECS   -- pause between ticker requests in seconds (default: 12)
    ALPHAVANTAGE_SYMBOLS      -- comma-separated ticker override (default: all 15)
    DATABASE_URL              -- Neon PostgreSQL connection string
"""

from __future__ import annotations

import os
import sys
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests
from sqlalchemy import MetaData, Table, create_engine, func, select
from sqlalchemy.dialects.postgresql import insert

# Make sure the app package is on the path when running directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Named logger so output is distinguishable in combined pipeline logs
logger = logging.getLogger("alphavantage_ingestor")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# The 15 tickers tracked on the website -- keep this in sync with the other ingest scripts
TARGET_TICKERS = [
    "KSS", "ALK", "NVS", "AXP", "FCX",
    "CSX", "DAL", "NTAP", "MRK", "COP",
    "BHP", "EA",
    "TSLA", "NVDA", "AAPL", "MSFT", "AMZN",
    "AMD", "META", "GOOGL", "GOOG", "PLTR",
    "MU", "NFLX",
    "NKE", "AAL", "BAC", "F", "INTC", "XOM", "T",
    "SOFI", "PLUG", "MARA", "SNAP", "COIN", "AMC", "RIVN", "CCL", "ENPH",
]

ALPHAVANTAGE_BASE_URL = "https://www.alphavantage.co/query"


def build_db_url() -> str:
    """Build the PostgreSQL connection string from environment variables.

    Prefers the full DATABASE_URL if set, otherwise assembles one
    from individual PG_* variables. Matches the pattern used in all other
    pipeline scripts so the same .env works everywhere.
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


def get_av_key() -> str:
    """Read the AlphaVantage API key from the environment and raise early if missing."""
    key = (os.getenv("ALPHAVANTAGE_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("Missing ALPHAVANTAGE_API_KEY environment variable.")
    return key


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def parse_av_timestamp(raw: Any) -> Optional[datetime]:
    """Parse AlphaVantage's compact timestamp format into a UTC-aware datetime.

    AlphaVantage uses a non-standard format: "YYYYMMDDTHHmmSS" with no separators
    and no timezone suffix. The API documentation states all times are UTC.

    Falls back to ISO 8601 parsing for any future format changes.
    """
    if raw is None:
        return None
    s = str(raw).strip()

    # Primary format: "20240101T120000"
    try:
        dt = datetime.strptime(s, "%Y%m%dT%H%M%S")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        pass

    # Fallback: ISO 8601 with optional "Z" suffix
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def parse_datetime_utc(raw: Any) -> Optional[datetime]:
    """Parse any reasonable datetime representation into a UTC-aware datetime.

    Used for reading stored DB timestamps back into Python.
    Returns None rather than raising if parsing fails.
    """
    if raw is None:
        return None
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw.astimezone(timezone.utc)
    s = str(raw).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt
    except Exception:
        return None


def clean_text(value: Any) -> Optional[str]:
    """Strip whitespace from a string field and return None if the result is empty."""
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def dedupe_keep_order(values: List[str]) -> List[str]:
    """Remove duplicate strings while preserving insertion order."""
    seen: set = set()
    out: List[str] = []
    for v in values:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


class AlphaVantageIngestor:
    """Fetches news from AlphaVantage NEWS_SENTIMENT and writes to stock_news_articles."""

    def __init__(self, db_url: Optional[str] = None):
        """Connect to the database and reflect the stock_news_articles table schema.

        Reflecting at startup means the upsert logic automatically handles any
        columns added to the table later without changes to this script.
        """
        if db_url is None:
            db_url = build_db_url()

        self.api_key = get_av_key()

        logger.info(f"Connecting to database at {db_url} ...")
        self.engine = create_engine(db_url)
        self.metadata = MetaData()

        logger.info("Reflecting required tables...")
        self.metadata.reflect(self.engine, only=["stock_news_articles"])

        if "stock_news_articles" not in self.metadata.tables:
            raise RuntimeError("Table 'stock_news_articles' does not exist in the database.")

        self.table: Table = self.metadata.tables["stock_news_articles"]
        # Cache column names so _store_articles can strip unknown fields safely
        self.article_cols = set(self.table.c.keys())
        logger.info(f"Reflected 'stock_news_articles'. columns={sorted(self.article_cols)}")

    def resolve_target_tickers(self) -> List[str]:
        """Return the list of tickers to process.

        If ALPHAVANTAGE_SYMBOLS is set, use that list. Otherwise fall back
        to the hardcoded TARGET_TICKERS that match the website.
        """
        env_symbols = (os.getenv("ALPHAVANTAGE_SYMBOLS") or "").strip()
        if env_symbols:
            tickers = [x.strip().upper() for x in env_symbols.split(",") if x.strip()]
            return dedupe_keep_order(tickers)
        return TARGET_TICKERS.copy()

    def get_last_published_at(self, ticker: str) -> Optional[datetime]:
        """Query the DB for the most recent published_at timestamp for a ticker.

        Used to set the time_from parameter so already-ingested articles are skipped.
        The upsert handles true duplicates regardless, but this reduces wasted API calls.
        """
        stmt = (
            select(func.max(self.table.c.published_at))
            .where(self.table.c.ticker == ticker)
        )
        with self.engine.begin() as conn:
            value = conn.execute(stmt).scalar_one_or_none()
        return parse_datetime_utc(value)

    def fetch_news(
        self,
        ticker: str,
        time_from: datetime,
        time_to: datetime,
        limit: int = 1000,
    ) -> Dict[str, Any]:
        """Call the AlphaVantage NEWS_SENTIMENT endpoint for a single ticker.

        AlphaVantage accepts tickers directly, so results are already filtered
        to articles that mention this specific stock.

        Note: The free tier returns a non-error 200 response with an "Information"
        or "Note" key when the daily limit is hit. This method raises RuntimeError
        in that case so the caller can stop processing remaining tickers.

        Args:
            ticker:    Stock ticker symbol (e.g. "AAPL").
            time_from: Start of the fetch window (UTC).
            time_to:   End of the fetch window (UTC).
            limit:     Max articles to return. AV hard maximum is 1000. Since each
                       ticker costs exactly 1 request regardless of article count,
                       always requesting the maximum gets the most data per quota unit.
        """
        params = {
            "function":  "NEWS_SENTIMENT",
            "tickers":   ticker,
            # AlphaVantage time format: YYYYMMDDTHHmm (no seconds, no timezone)
            "time_from": time_from.strftime("%Y%m%dT%H%M"),
            "time_to":   time_to.strftime("%Y%m%dT%H%M"),
            "limit":     limit,
            "apikey":    self.api_key,
        }
        resp = requests.get(ALPHAVANTAGE_BASE_URL, params=params, timeout=30)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"AlphaVantage request failed ({resp.status_code}): {resp.text[:400]}"
            )

        data = resp.json()

        # Rate limit and other informational messages come back as 200 responses
        # with an "Information" or "Note" key instead of the expected "feed" key
        if "Information" in data or "Note" in data:
            msg = data.get("Information") or data.get("Note") or ""
            raise RuntimeError(f"AlphaVantage API limit reached: {msg}")

        return data

    def _get_ticker_relevance(
        self, ticker: str, ticker_sentiment: List[Dict[str, Any]]
    ) -> Optional[float]:
        """Extract the relevance score for a specific ticker from the ticker_sentiment list.

        Each AlphaVantage article includes a list of all mentioned tickers with
        individual relevance scores. This finds the score for the ticker being ingested.
        Returns None if the ticker is not found in the list.
        """
        for ts in (ticker_sentiment or []):
            if (ts.get("ticker") or "").upper() == ticker.upper():
                try:
                    return float(ts["relevance_score"])
                except (KeyError, TypeError, ValueError):
                    return None
        return None

    def normalize_article(self, ticker: str, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Map a raw AlphaVantage feed item to the stock_news_articles schema.

        Returns None for articles missing a URL or a parseable publish timestamp.
        Stores the article summary as both description and snippet since AV does
        not distinguish between the two.
        """
        url = clean_text(item.get("url"))
        if not url:
            return None

        published_at = parse_av_timestamp(item.get("time_published"))
        if published_at is None:
            return None

        # Pull relevance score for this specific ticker from the nested list
        ticker_sentiment = item.get("ticker_sentiment") or []
        relevance = self._get_ticker_relevance(ticker, ticker_sentiment)

        # "summary" is the best available text -- it is the full lead paragraph
        summary = clean_text(item.get("summary"))
        title = clean_text(item.get("title"))

        return {
            "ticker":         ticker.upper(),
            "url":            url,
            "title":          title,
            "source":         clean_text(item.get("source")),
            "description":    summary,
            "snippet":        summary,
            "image_url":      clean_text(item.get("banner_image")),
            "language":       "en",
            "published_at":   published_at,
            "relevance_score": relevance,
        }

    def _store_articles(self, records: List[Dict[str, Any]]) -> int:
        """Upsert a batch of normalized article records into stock_news_articles.

        Uses PostgreSQL ON CONFLICT DO UPDATE so re-running on an overlapping
        date window refreshes metadata without creating duplicate rows.
        The unique constraint is (ticker, url).
        """
        if not records:
            return 0

        # Strip keys that are not columns in the table to prevent insert errors
        filtered = [{k: v for k, v in r.items() if k in self.article_cols} for r in records]
        # Drop records missing required fields
        filtered = [r for r in filtered if r.get("ticker") and r.get("url")]
        if not filtered:
            return 0

        with self.engine.begin() as conn:
            stmt = insert(self.table).values(filtered)
            stmt = stmt.on_conflict_do_update(
                index_elements=["ticker", "url"],
                set_={
                    "title":           stmt.excluded.title,
                    "source":          stmt.excluded.source,
                    "description":     stmt.excluded.description,
                    "snippet":         stmt.excluded.snippet,
                    "image_url":       stmt.excluded.image_url,
                    "language":        stmt.excluded.language,
                    "published_at":    stmt.excluded.published_at,
                    "relevance_score": stmt.excluded.relevance_score,
                },
            )
            result = conn.execute(stmt)
            return result.rowcount or 0

    def ingest(
        self,
        tickers: Optional[List[str]] = None,
        lookback_days: int = 3,
        limit_per_ticker: int = 1000,
        request_delay_secs: float = 12.0,
    ) -> None:
        """Fetch and store news for all target tickers from AlphaVantage.

        Makes one API call per ticker. Stops early if the rate limit is hit so
        remaining daily quota is not wasted on error responses.

        The 12-second delay between tickers keeps requests under the 5/min limit.
        15 tickers x 12s = 3 minutes total runtime, which is acceptable.

        Args:
            tickers:             Override ticker list. Defaults to TARGET_TICKERS.
            lookback_days:       Days back to fetch if no existing articles.
            limit_per_ticker:    Max articles per API call. Set to 1000 (AV hard max)
                                 since each ticker costs 1 request regardless of count.
            request_delay_secs:  Seconds to wait between ticker requests.
        """
        if tickers is None:
            tickers = self.resolve_target_tickers()
        tickers = dedupe_keep_order([t.strip().upper() for t in tickers if t.strip()])

        # All params can be overridden via environment variables for Docker runs
        lookback_days = int(os.getenv("ALPHAVANTAGE_LOOKBACK_DAYS", str(lookback_days)))
        limit_per_ticker = int(os.getenv("ALPHAVANTAGE_LIMIT", str(limit_per_ticker)))
        request_delay_secs = float(os.getenv("ALPHAVANTAGE_DELAY_SECS", str(request_delay_secs)))

        now = utc_now()

        logger.info(
            f"[AV-INGEST] start tickers={len(tickers)} "
            f"lookback_days={lookback_days} limit_per_ticker={limit_per_ticker} "
            f"delay_secs={request_delay_secs}"
        )

        requests_made = 0
        total_seen = 0
        total_written = 0
        skipped = 0

        for idx, ticker in enumerate(tickers, start=1):
            # Determine the fetch window -- start from the last ingested article
            # or fall back to the lookback floor
            last_published = self.get_last_published_at(ticker)
            floor_dt = now - timedelta(days=lookback_days)
            time_from = max(last_published, floor_dt) if last_published else floor_dt
            time_to = now

            logger.info(
                f"[AV-INGEST] {ticker} ({idx}/{len(tickers)}) "
                f"window={time_from.strftime('%Y-%m-%d')} -> {time_to.strftime('%Y-%m-%d')}"
            )

            try:
                payload = self.fetch_news(ticker, time_from, time_to, limit=limit_per_ticker)
            except RuntimeError as e:
                # Break on rate-limit to avoid burning remaining quota on error responses
                logger.error(f"[AV-INGEST] {ticker} fetch error: {e}")
                break

            requests_made += 1

            items = payload.get("feed") or []
            logger.info(f"[AV-INGEST] {ticker} returned={len(items)}")

            # Normalize all articles for this ticker before writing as a batch
            records: List[Dict[str, Any]] = []
            for item in items:
                total_seen += 1
                record = self.normalize_article(ticker, item)
                if record is None:
                    skipped += 1
                    continue
                records.append(record)

            if records:
                written = self._store_articles(records)
                total_written += written
                logger.info(f"[AV-INGEST] {ticker} stored={written}")

            # Sleep between tickers to respect the 5 requests/minute rate limit
            if idx < len(tickers):
                time.sleep(request_delay_secs)

        logger.info(
            f"[AV-INGEST] DONE requests={requests_made} "
            f"seen={total_seen} written={total_written} skipped={skipped}"
        )


def run_alphavantage_ingest_from_env(db_url: Optional[str] = None) -> None:
    """Run AlphaVantage news ingest using environment variable configuration."""
    ing = AlphaVantageIngestor(db_url=db_url)
    ing.ingest()


if __name__ == "__main__":
    ing = AlphaVantageIngestor()
    ing.ingest()
