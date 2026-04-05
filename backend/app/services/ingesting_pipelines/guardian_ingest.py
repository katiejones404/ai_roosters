"""
guardian_ingest.py

Ingests financial news articles from The Guardian Open Platform API for each
of the 15 target tickers and writes them into stock_news_articles.

The Guardian is the most valuable of the three free api sources for historical
backfill because its free tier has no hard lookback limit, we can fetch articles
from years ago, not just the past 29-30 days. The business section covers earnings,
mergers, and market movements for all major stocks tracked on the site.

Free tier limits:
    - 500 requests per day
    - No lookback date restriction (full archive available)
    - 50 articles per page

With 15 tickers and up to 5 pages each, this uses at most 75 of the 500 daily
requests, leaving plenty of quota for additional backfill runs.

To get a Guardian API key:
    1. Register at https://open-platform.theguardian.com/access/
    2. Set GUARDIAN_API_KEY in your .env file

Usage:
    docker compose --profile pipeline run --rm pipeline \
        python -m app.services.ingesting_pipelines.guardian_ingest

Environment variables:
    GUARDIAN_API_KEY          -- (required) Guardian Open Platform API key
    GUARDIAN_LOOKBACK_DAYS    -- days back to fetch on initial run (default: 30)
    GUARDIAN_MAX_PAGES        -- max pages per ticker (default: 5)
    GUARDIAN_PAGE_SIZE        -- articles per API page (default: 50, max: 50)
    GUARDIAN_SYMBOLS          -- comma-separated ticker override (default: all 15)
    DATABASE_URL              -- Neon PostgreSQL connection string
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

# Named logger so output is distinguishable in combined pipeline logs
logger = logging.getLogger("guardian_ingestor")
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

# The Guardian does not support ticker symbol filtering, so we search by company
# name. These queries are tuned to minimize false positives for ambiguous tickers
# like "EA" (Electronic Arts) or "CSX" (the railroad company).
TICKER_QUERIES: Dict[str, str] = {
    "KSS":  "Kohl's department store",
    "ALK":  "Alaska Airlines",
    "NVS":  "Novartis",
    "AXP":  "American Express",
    "FCX":  "Freeport-McMoRan",
    "CSX":  "CSX Corporation railroad",
    "DAL":  "Delta Air Lines",
    "NTAP": "NetApp",
    "MRK":  "Merck",
    "COP":  "ConocoPhillips",
    "BHP":  "BHP",
    "EA":   "Electronic Arts",
    "TSLA": "Tesla",
    "NVDA": "Nvidia",
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "AMZN": "Amazon",
    "AMD":  "Advanced Micro Devices",
    "META": "Meta Platforms Facebook",
    "GOOGL": "Alphabet Google",
    "GOOG": "Alphabet Google",
    "PLTR": "Palantir",
    "MU":   "Micron Technology",
    "NFLX": "Netflix",
    "NKE":  "Nike",
    "AAL":  "American Airlines",
    "BAC":  "Bank of America",
    "F":    "Ford Motor Company",
    "INTC": "Intel",
    "XOM":  "ExxonMobil",
    "T":    "AT&T",
    "SOFI": "SoFi Technologies",
    "PLUG": "Plug Power",
    "MARA": "Marathon Digital",
    "SNAP": "Snap Snapchat",
    "COIN": "Coinbase",
    "AMC":  "AMC Entertainment",
    "RIVN": "Rivian",
    "CCL":  "Carnival Corporation",
    "ENPH": "Enphase Energy",
}

GUARDIAN_BASE_URL = "https://content.guardianapis.com/search"


def build_db_url() -> str:
    """Build the PostgreSQL connection string from environment variables.

    Prefers the full DATABASE_URL if set, otherwise assembles one from
    individual PG_* variables. Matches the pattern used in all other
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


def get_guardian_key() -> str:
    """Read the Guardian API key from the environment and raise early if missing."""
    key = (os.getenv("GUARDIAN_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("Missing GUARDIAN_API_KEY environment variable.")
    return key


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def parse_datetime_utc(raw: Any) -> Optional[datetime]:
    """Parse any reasonable datetime representation into a UTC-aware datetime.

    Handles:
    - Python datetime objects (naive assumed UTC)
    - ISO 8601 strings including "Z" suffix (Guardian uses "2024-01-01T12:00:00Z")
    - Returns None rather than raising if parsing fails.
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
        # Guardian returns ISO 8601 with "Z" suffix
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


class GuardianIngestor:
    """Fetches news from The Guardian API and writes results to stock_news_articles."""

    def __init__(self, db_url: Optional[str] = None):
        """Connect to the database and reflect the stock_news_articles table schema.

        Reflecting at startup means the upsert logic automatically handles any
        columns added to the table later without changes to this script.
        """
        if db_url is None:
            db_url = build_db_url()

        self.api_key = get_guardian_key()

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

        If GUARDIAN_SYMBOLS is set, use that list. Otherwise fall back to the
        hardcoded TARGET_TICKERS that match the website.
        """
        env_symbols = (os.getenv("GUARDIAN_SYMBOLS") or "").strip()
        if env_symbols:
            tickers = [x.strip().upper() for x in env_symbols.split(",") if x.strip()]
            return dedupe_keep_order(tickers)
        return TARGET_TICKERS.copy()

    def get_last_published_at(self, ticker: str) -> Optional[datetime]:
        """Query the DB for the most recent published_at timestamp for a ticker.

        Used to set the from-date parameter so we skip articles already ingested.
        The upsert handles true duplicates regardless, but this avoids unnecessary
        API calls when re-running the script on an already-populated table.
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
        """Make a single paginated request to the Guardian search endpoint.

        Requests the trailText (article summary) and thumbnail fields via
        show-fields so we have content to populate description and image_url.

        The "business" section filter is intentionally omitted here because some
        relevant articles appear in technology, environment, or US news sections.
        The keyword query is tight enough to keep results relevant.

        Args:
            query:     Company name search string.
            from_dt:   Start of the fetch window.
            to_dt:     End of the fetch window.
            page:      Page number starting at 1.
            page_size: Articles per page (Guardian max is 50).
        """
        params = {
            "api-key":    self.api_key,
            "q":          query,
            "from-date":  from_dt.strftime("%Y-%m-%d"),
            "to-date":    to_dt.strftime("%Y-%m-%d"),
            "page-size":  page_size,
            "page":       page,
            # Request extra fields -- trailText is the article lead sentence
            "show-fields": "trailText,thumbnail",
            "order-by":   "newest",
        }
        resp = requests.get(GUARDIAN_BASE_URL, params=params, timeout=30)

        # 401 means the API key is invalid or missing
        if resp.status_code == 401:
            raise RuntimeError(
                "Guardian API returned 401 Unauthorized. "
                "Check that GUARDIAN_API_KEY is set correctly in .env."
            )
        # 429 means the daily quota is exhausted
        if resp.status_code == 429:
            raise RuntimeError(
                "Guardian API rate limit hit (500 req/day on free tier). Try again tomorrow."
            )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Guardian API request failed ({resp.status_code}): {resp.text[:400]}"
            )

        data = resp.json()

        # Guardian always wraps results in a "response" object
        inner = data.get("response") or {}
        if inner.get("status") != "ok":
            raise RuntimeError(
                f"Guardian API non-ok status: {inner.get('status')} "
                f"message={inner.get('message')}"
            )
        return inner

    def normalize_article(self, ticker: str, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Map a raw Guardian result item to the stock_news_articles schema.

        Guardian articles always have a URL (webUrl) and publication date, but
        checking both defensively prevents unexpected nulls from causing DB errors.

        The "fields" object contains the optional trailText and thumbnail that
        were requested via show-fields. Both are nullable.
        """
        url = clean_text(item.get("webUrl"))
        if not url:
            return None

        published_at = parse_datetime_utc(item.get("webPublicationDate"))
        if published_at is None:
            return None

        # "fields" contains the extra data requested via show-fields
        fields = item.get("fields") or {}
        trail_text = clean_text(fields.get("trailText"))
        thumbnail = clean_text(fields.get("thumbnail"))

        title = clean_text(item.get("webTitle"))
        section = clean_text(item.get("sectionName"))

        return {
            "ticker":         ticker.upper(),
            "url":            url,
            "title":          title,
            # Use the section name as source since Guardian articles are self-sourced
            "source":         f"The Guardian - {section}" if section else "The Guardian",
            "description":    trail_text,
            "snippet":        trail_text,
            "image_url":      thumbnail,
            "language":       "en",
            "published_at":   published_at,
            # Guardian does not provide a relevance score
            "relevance_score": None,
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
        lookback_days: int = 10,
        max_pages: int = 2,
        page_size: int = 10,
        flush_batch_size: int = 200,
    ) -> None:
        """Fetch and store articles for all target tickers from The Guardian.

        For each ticker:
        1. Determine the fetch window (last_published_at or lookback_days floor).
        2. Page through Guardian results up to max_pages.
        3. Buffer normalized records and flush to DB in batches.
        4. Stop paging early when the API returns fewer results than requested.

        For historical backfill, set GUARDIAN_LOOKBACK_DAYS to a large number
        (e.g., 1095 for three years) and GUARDIAN_MAX_PAGES to 20 or more.
        Guardian has no lookback restriction on the free tier.

        Args:
            tickers:         Override ticker list. Defaults to TARGET_TICKERS.
            lookback_days:   Days back to fetch if no existing articles (default 30).
            max_pages:       Max pages per ticker (50 articles each).
            page_size:       Articles per API page. Guardian max is 50.
            flush_batch_size:Records to accumulate before writing to DB.
        """
        if tickers is None:
            tickers = self.resolve_target_tickers()
        tickers = dedupe_keep_order([t.strip().upper() for t in tickers if t.strip()])

        # Environment variable overrides allow tuning without code changes
        lookback_days = int(os.getenv("GUARDIAN_LOOKBACK_DAYS", str(lookback_days)))
        max_pages = int(os.getenv("GUARDIAN_MAX_PAGES", str(max_pages)))
        page_size = min(int(os.getenv("GUARDIAN_PAGE_SIZE", str(page_size))), 50)

        now = utc_now()

        logger.info(
            f"[GUARDIAN-INGEST] start tickers={len(tickers)} "
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
            logger.info(f"[GUARDIAN-INGEST] flushed batch={len(buffer)} written={written}")
            buffer = []

        for idx, ticker in enumerate(tickers, start=1):
            query = TICKER_QUERIES.get(ticker, ticker)

            # Start from the most recent article already in the DB, or the lookback floor
            last_published = self.get_last_published_at(ticker)
            floor_dt = now - timedelta(days=lookback_days)
            from_dt = max(last_published, floor_dt) if last_published else floor_dt
            to_dt = now

            logger.info(
                f"[GUARDIAN-INGEST] {ticker} ({idx}/{len(tickers)}) "
                f"query='{query}' window={from_dt.date()} -> {to_dt.date()}"
            )

            # Track total results for early page termination
            total_pages: Optional[int] = None

            for page in range(1, max_pages + 1):
                try:
                    inner = self.fetch_page(query, from_dt, to_dt, page, page_size)
                except RuntimeError as e:
                    logger.error(f"[GUARDIAN-INGEST] {ticker} page={page} error: {e}")
                    break

                requests_made += 1

                # Capture pagination metadata on first page
                if total_pages is None:
                    total_pages = int(inner.get("pages") or 0)

                items = inner.get("results") or []
                logger.info(
                    f"[GUARDIAN-INGEST] {ticker} page={page}/{total_pages} "
                    f"returned={len(items)}"
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

                # Stop if we've already fetched all pages the API reported
                if total_pages is not None and page >= total_pages:
                    break

        # Write any remaining records that didn't fill a full batch
        flush()

        logger.info(
            f"[GUARDIAN-INGEST] DONE requests={requests_made} "
            f"seen={total_seen} written={total_written} skipped={skipped}"
        )


def run_guardian_ingest_from_env(db_url: Optional[str] = None) -> None:
    """Run Guardian news ingest using environment variable configuration."""
    ing = GuardianIngestor(db_url=db_url)
    ing.ingest()


if __name__ == "__main__":
    ing = GuardianIngestor()
    ing.ingest()
