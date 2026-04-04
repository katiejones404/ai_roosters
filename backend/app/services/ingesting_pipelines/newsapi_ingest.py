"""
newsapi_ingest.py

Ingests recent financial news articles from the NewsAPI (newsapi.org) for each
of the 15 target tickers and writes them into the stock_news_articles table.

NewsAPI free tier limits:
    - 100 requests per day
    - Articles up to 29 days old
    - Page size max 100

Run this daily alongside daily_news_ingest.py to supplement Marketaux coverage.

Usage:
    docker compose --profile pipeline run --rm pipeline \
        python -m app.services.ingesting_pipelines.newsapi_ingest

Environment variables:
    NEWSAPI_API_KEY         -- (required) NewsAPI developer key
    NEWSAPI_LOOKBACK_DAYS   -- how many days back to fetch (default: 7, max: 29)
    NEWSAPI_MAX_PAGES       -- max pages to fetch per ticker (default: 5)
    NEWSAPI_PAGE_SIZE       -- articles per page (default: 100, max: 100)
    NEWSAPI_SYMBOLS         -- comma-separated ticker override (default: all 15)
    DATABASE_URL            -- Neon PostgreSQL connection string
"""

from __future__ import annotations

import os
import sys
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests
from sqlalchemy import MetaData, Table, create_engine, func, select
from sqlalchemy.dialects.postgresql import insert

# Make sure the app package is on the path when running directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up a named logger so output is distinguishable in combined pipeline logs
logger = logging.getLogger("newsapi_ingestor")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Tickers tracked on the website -- keep this in sync with the other ingest scripts
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

# NewsAPI works best with company name queries rather than raw tickers.
# Tickers like "EA" or "CSX" return unrelated results without a disambiguating keyword.
TICKER_QUERIES: Dict[str, str] = {
    "KSS":  "Kohl's retail",
    "ALK":  "Alaska Air airline",
    "NVS":  "Novartis pharma",
    "AXP":  "American Express",
    "FCX":  "Freeport-McMoRan copper",
    "CSX":  "CSX railroad",
    "DAL":  "Delta Air Lines",
    "NTAP": "NetApp storage",
    "MRK":  "Merck pharmaceutical",
    "COP":  "ConocoPhillips oil",
    "BHP":  "BHP mining",
    "EA":   "Electronic Arts gaming",
    "TSLA": "Tesla electric vehicle",
    "NVDA": "NVIDIA GPU",
    "AAPL": "Apple Inc",
    "MSFT": "Microsoft",
    "AMZN": "Amazon",
    "AMD":  "AMD semiconductor",
    "META": "Meta Facebook social media",
    "GOOGL": "Alphabet Google",
    "GOOG": "Alphabet Google",
    "PLTR": "Palantir data analytics",
    "MU":   "Micron memory chip",
    "NFLX": "Netflix streaming",
    "NKE":  "Nike athletic",
    "AAL":  "American Airlines",
    "BAC":  "Bank of America",
    "F":    "Ford Motor",
    "INTC": "Intel chip",
    "XOM":  "ExxonMobil oil",
    "T":    "AT&T telecom",
    "SOFI": "SoFi financial",
    "PLUG": "Plug Power hydrogen",
    "MARA": "Marathon Digital bitcoin",
    "SNAP": "Snap Snapchat",
    "COIN": "Coinbase crypto",
    "AMC":  "AMC Entertainment",
    "RIVN": "Rivian electric truck",
    "CCL":  "Carnival cruise",
    "ENPH": "Enphase solar",
}

NEWSAPI_BASE_URL = "https://newsapi.org/v2/everything"


def build_db_url() -> str:
    """Build the PostgreSQL connection string from environment variables.

    Prefers the full DATABASE_URL if set, otherwise assembles one
    from individual PG_* variables. Matches the pattern used across
    all other pipeline scripts.
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


def get_newsapi_key() -> str:
    """Read the NewsAPI key from the environment and raise early if missing."""
    key = (os.getenv("NEWSAPI_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("Missing NEWSAPI_API_KEY environment variable.")
    return key


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def parse_datetime_utc(raw: Any) -> Optional[datetime]:
    """Parse any reasonable datetime representation into a UTC-aware datetime.

    Handles:
    - Python datetime objects (naive assumed UTC)
    - ISO 8601 strings including "Z" suffix
    - Returns None if parsing fails rather than raising.
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
        # NewsAPI returns ISO 8601 with "Z" suffix, which Python < 3.11 does not parse natively
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


class NewsApiIngestor:
    """Fetches news from NewsAPI and writes results to stock_news_articles."""

    def __init__(self, db_url: Optional[str] = None):
        """Connect to the database and reflect the stock_news_articles table schema.

        Reflecting the schema at startup lets the upsert logic stay in sync with
        any future column additions without requiring code changes here.
        """
        if db_url is None:
            db_url = build_db_url()

        self.api_key = get_newsapi_key()

        logger.info(f"Connecting to database at {db_url} ...")
        self.engine = create_engine(db_url)
        self.metadata = MetaData()

        logger.info("Reflecting required tables...")
        self.metadata.reflect(self.engine, only=["stock_news_articles"])

        if "stock_news_articles" not in self.metadata.tables:
            raise RuntimeError("Table 'stock_news_articles' does not exist in the database.")

        self.table: Table = self.metadata.tables["stock_news_articles"]
        # Store column names so _store_articles can strip unknown fields safely
        self.article_cols = set(self.table.c.keys())
        logger.info(f"Reflected 'stock_news_articles'. columns={sorted(self.article_cols)}")

    def resolve_target_tickers(self) -> List[str]:
        """Return the list of tickers to process.

        If NEWSAPI_SYMBOLS is set, use that list. Otherwise fall back to the
        hardcoded TARGET_TICKERS that match the website.
        """
        env_symbols = (os.getenv("NEWSAPI_SYMBOLS") or "").strip()
        if env_symbols:
            tickers = [x.strip().upper() for x in env_symbols.split(",") if x.strip()]
            return dedupe_keep_order(tickers)
        return TARGET_TICKERS.copy()

    def get_last_published_at(self, ticker: str) -> Optional[datetime]:
        """Query the DB for the most recent published_at timestamp for a ticker.

        Used to calculate the start of the fetch window so duplicate articles
        are minimized (though the upsert handles true duplicates anyway).
        """
        stmt = (
            select(func.max(self.table.c.published_at))
            .where(self.table.c.ticker == ticker)
        )
        with self.engine.begin() as conn:
            value = conn.execute(stmt).scalar_one_or_none()
        return parse_datetime_utc(value)

    def fetch_page(
        self,
        query: str,
        from_dt: datetime,
        to_dt: datetime,
        page: int,
        page_size: int,
    ) -> Dict[str, Any]:
        """Make a single paginated request to the NewsAPI /everything endpoint.

        Raises RuntimeError on HTTP errors or if the daily rate limit is hit.
        Free tier: 100 requests/day, 100 articles/page, articles from last 29 days.
        """
        params = {
            "apiKey": self.api_key,
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            # NewsAPI expects ISO 8601 without timezone offset
            "from": from_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "to":   to_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "pageSize": page_size,
            "page": page,
        }
        resp = requests.get(NEWSAPI_BASE_URL, params=params, timeout=30)

        # 429 means the daily quota is exhausted
        if resp.status_code == 429:
            raise RuntimeError(
                "NewsAPI rate limit hit (100 req/day on free tier). Try again tomorrow."
            )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"NewsAPI request failed ({resp.status_code}): {resp.text[:400]}"
            )
        return resp.json()

    def normalize_article(self, ticker: str, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Map a raw NewsAPI article dict to the stock_news_articles schema.

        Returns None for articles missing a URL (unfetchable) or a published date,
        and for the placeholder URL that NewsAPI returns when content is removed.
        """
        url = clean_text(item.get("url"))
        # NewsAPI substitutes this URL for removed/paywalled content
        if not url or url == "https://removed.com":
            return None

        published_at = parse_datetime_utc(item.get("publishedAt"))
        if published_at is None:
            return None

        # "source" is a nested object {"id": ..., "name": ...}
        source_obj = item.get("source") or {}
        source_name = (
            clean_text(source_obj.get("name"))
            if isinstance(source_obj, dict)
            else None
        )

        description = clean_text(item.get("description"))
        content = clean_text(item.get("content"))
        # NewsAPI truncates article content at 200 chars -- use description as the snippet
        snippet = description

        return {
            "ticker": ticker.upper(),
            "url": url,
            "title": clean_text(item.get("title")),
            "source": source_name,
            "description": description or content,
            "snippet": snippet,
            "image_url": clean_text(item.get("urlToImage")),
            "language": "en",
            "published_at": published_at,
            # NewsAPI does not provide per-article relevance scores
            "relevance_score": None,
        }

    def _store_articles(self, records: List[Dict[str, Any]]) -> int:
        """Upsert a batch of normalized article records into stock_news_articles.

        Uses PostgreSQL ON CONFLICT DO UPDATE so re-running the script on the
        same date range refreshes metadata without creating duplicates.
        The unique constraint is (ticker, url).
        """
        if not records:
            return 0

        # Strip any keys that don't exist in the table to avoid insert errors
        filtered = [{k: v for k, v in r.items() if k in self.article_cols} for r in records]
        # Drop records that are missing required fields
        filtered = [r for r in filtered if r.get("ticker") and r.get("url")]
        if not filtered:
            return 0

        with self.engine.begin() as conn:
            stmt = insert(self.table).values(filtered)
            stmt = stmt.on_conflict_do_update(
                index_elements=["ticker", "url"],
                set_={
                    "title":          stmt.excluded.title,
                    "source":         stmt.excluded.source,
                    "description":    stmt.excluded.description,
                    "snippet":        stmt.excluded.snippet,
                    "image_url":      stmt.excluded.image_url,
                    "language":       stmt.excluded.language,
                    "published_at":   stmt.excluded.published_at,
                    "relevance_score":stmt.excluded.relevance_score,
                },
            )
            result = conn.execute(stmt)
            return result.rowcount or 0

    def ingest(
        self,
        tickers: Optional[List[str]] = None,
        lookback_days: int = 7,
        max_pages: int = 5,
        page_size: int = 100,
        flush_batch_size: int = 200,
    ) -> None:
        """Fetch and store recent articles for all target tickers.

        For each ticker:
        1. Determine the fetch window (last_published_at or lookback_days floor)
        2. Page through NewsAPI results up to max_pages
        3. Buffer normalized records and flush to DB in batches
        4. Stop paging early when the API returns fewer results than requested

        Args:
            tickers:         Override list of tickers. Defaults to TARGET_TICKERS.
            lookback_days:   How far back to fetch if no existing articles. Max 29 on free tier.
            max_pages:       Max pages to request per ticker (100 articles each).
            page_size:       Articles per API page. Max 100 on free tier.
            flush_batch_size:How many records to accumulate before writing to DB.
        """
        if tickers is None:
            tickers = self.resolve_target_tickers()
        tickers = dedupe_keep_order([t.strip().upper() for t in tickers if t.strip()])

        # Environment variable overrides allow tuning without code changes
        lookback_days = int(os.getenv("NEWSAPI_LOOKBACK_DAYS", str(lookback_days)))
        max_pages = int(os.getenv("NEWSAPI_MAX_PAGES", str(max_pages)))
        page_size = min(int(os.getenv("NEWSAPI_PAGE_SIZE", str(page_size))), 100)

        # Clamp to free tier maximum (29 days)
        lookback_days = min(lookback_days, 29)
        now = utc_now()

        logger.info(
            f"[NEWSAPI-INGEST] start tickers={len(tickers)} "
            f"lookback_days={lookback_days} max_pages={max_pages} page_size={page_size}"
        )

        # Shared buffer for batched DB writes
        buffer: List[Dict[str, Any]] = []
        requests_made = 0
        total_seen = 0
        total_written = 0
        skipped = 0

        def flush() -> None:
            """Write the current buffer to the database and reset it."""
            nonlocal total_written, buffer
            if not buffer:
                return
            written = self._store_articles(buffer)
            total_written += written
            logger.info(f"[NEWSAPI-INGEST] flushed batch={len(buffer)} written={written}")
            buffer = []

        for idx, ticker in enumerate(tickers, start=1):
            query = TICKER_QUERIES.get(ticker, ticker)

            # Start the fetch window from the most recent article we already have,
            # falling back to the lookback floor if the table is empty for this ticker
            last_published = self.get_last_published_at(ticker)
            floor_dt = now - timedelta(days=lookback_days)
            from_dt = max(last_published, floor_dt) if last_published else floor_dt
            to_dt = now

            logger.info(
                f"[NEWSAPI-INGEST] {ticker} ({idx}/{len(tickers)}) "
                f"query='{query}' window={from_dt.date()} -> {to_dt.date()}"
            )

            # Track total results for this ticker so we can stop early
            total_results: Optional[int] = None

            for page in range(1, max_pages + 1):
                try:
                    payload = self.fetch_page(query, from_dt, to_dt, page, page_size)
                except RuntimeError as e:
                    logger.error(f"[NEWSAPI-INGEST] {ticker} page={page} error: {e}")
                    break

                requests_made += 1
                status = payload.get("status")

                if status != "ok":
                    logger.warning(
                        f"[NEWSAPI-INGEST] {ticker} page={page} bad status={status} "
                        f"code={payload.get('code')} msg={payload.get('message')}"
                    )
                    break

                # Capture total results count on first page so we know when to stop paging
                if total_results is None:
                    total_results = int(payload.get("totalResults") or 0)

                items = payload.get("articles") or []
                logger.info(
                    f"[NEWSAPI-INGEST] {ticker} page={page} "
                    f"returned={len(items)} total={total_results}"
                )

                if not items:
                    break

                for item in items:
                    total_seen += 1
                    record = self.normalize_article(ticker, item)
                    if record is None:
                        skipped += 1
                        continue
                    buffer.append(record)
                    if len(buffer) >= flush_batch_size:
                        flush()

                # If we got fewer results than requested, there are no more pages
                if len(items) < page_size:
                    break

        # Write any remaining records that didn't fill a full batch
        flush()

        logger.info(
            f"[NEWSAPI-INGEST] DONE requests={requests_made} "
            f"seen={total_seen} written={total_written} skipped={skipped}"
        )


if __name__ == "__main__":
    ing = NewsApiIngestor()
    ing.ingest()
