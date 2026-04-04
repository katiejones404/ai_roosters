from __future__ import annotations

import os
import sys
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests
from sqlalchemy import MetaData, Table, create_engine, func, select
from sqlalchemy.dialects.postgresql import insert

# Optional: project root on path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger("stock_news_ingestor")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Keep this aligned with the stocks shown on the website
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


def get_marketaux_token() -> str:
    token = (os.getenv("MARKETAUX_API_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("Missing MARKETAUX_API_TOKEN environment variable.")
    return token


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_api_datetime(dt: datetime) -> str:
    dt = dt.astimezone(timezone.utc).replace(microsecond=0)
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def parse_datetime_utc(raw: Any) -> Optional[datetime]:
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
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def dedupe_keep_order(values: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for v in values:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


class StockNewsIngestor:
    def __init__(self, db_url: Optional[str] = None):
        if db_url is None:
            db_url = build_db_url()

        self.api_token = get_marketaux_token()
        self.base_url = os.getenv("MARKETAUX_BASE_URL", "https://api.marketaux.com/v1/news/all").strip()

        logger.info(f"Connecting to database at {db_url} ...")
        self.engine = create_engine(db_url)
        self.metadata = MetaData()

        logger.info("Reflecting required tables...")
        self.metadata.reflect(self.engine, only=["stock_news_articles"])

        if "stock_news_articles" not in self.metadata.tables:
            raise RuntimeError("Table 'stock_news_articles' does not exist in the database.")

        self.stock_news_articles: Table = self.metadata.tables["stock_news_articles"]
        self.article_cols = set(self.stock_news_articles.c.keys())

        logger.info(f"Reflected 'stock_news_articles'. columns={sorted(self.article_cols)}")

        required_article_cols = {"ticker", "url", "published_at"}
        missing_article_cols = [c for c in required_article_cols if c not in self.article_cols]
        if missing_article_cols:
            raise RuntimeError(
                f"'stock_news_articles' missing required columns: {missing_article_cols}"
            )

    def resolve_target_tickers(self) -> List[str]:
        # Optional override if you ever want to test a smaller subset
        env_symbols = (os.getenv("NEWS_SYMBOLS") or "").strip()
        if env_symbols:
            tickers = [x.strip().upper() for x in env_symbols.split(",") if x.strip()]
            tickers = dedupe_keep_order(tickers)
            logger.info(f"Using NEWS_SYMBOLS override with {len(tickers)} ticker(s).")
            return tickers

        logger.info(f"Using hardcoded website ticker universe with {len(TARGET_TICKERS)} ticker(s).")
        return TARGET_TICKERS.copy()

    def get_last_published_at_for_ticker(self, ticker: str) -> Optional[datetime]:
        stmt = (
            select(func.max(self.stock_news_articles.c.published_at))
            .where(self.stock_news_articles.c.ticker == ticker)
        )

        with self.engine.begin() as conn:
            value = conn.execute(stmt).scalar_one_or_none()

        return parse_datetime_utc(value)

    def resolve_published_after(
        self,
        ticker: str,
        lookback_hours: int,
        overlap_minutes: int,
    ) -> datetime:
        floor_dt = utc_now() - timedelta(hours=lookback_hours)
        last_dt = self.get_last_published_at_for_ticker(ticker)

        if last_dt is None:
            return floor_dt

        candidate = last_dt - timedelta(minutes=overlap_minutes)
        return max(candidate, floor_dt)

    def fetch_news_page(
        self,
        symbol: str,
        published_after: datetime,
        published_before: datetime,
        page: int,
        limit: int,
        language: str = "en",
    ) -> Dict[str, Any]:
        params = {
            "api_token": self.api_token,
            "symbols": symbol,
            "filter_entities": "true",
            "must_have_entities": "true",
            "group_similar": "true",
            "published_after": to_api_datetime(published_after),
            "published_before": to_api_datetime(published_before),
            "page": page,
            "limit": limit,
            "language": language,
            "sort": "published_at",
        }

        resp = requests.get(self.base_url, params=params, timeout=60)
        if resp.status_code >= 400:
            raise RuntimeError(f"Marketaux request failed ({resp.status_code}): {resp.text[:500]}")
        return resp.json()

    def normalize_article(
        self,
        symbol: str,
        item: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        url = clean_text(item.get("url"))
        if not url:
            return None

        published_at = parse_datetime_utc(item.get("published_at"))
        if published_at is None:
            return None

        relevance_score = item.get("relevance_score")
        matched_score = None

        for ent in (item.get("entities") or []):
            ent_symbol = clean_text((ent or {}).get("symbol"))
            if ent_symbol and ent_symbol.upper() == symbol.upper():
                matched_score = (ent or {}).get("match_score")
                break

        final_score = matched_score if matched_score is not None else relevance_score

        return {
            "ticker": symbol.upper(),
            "url": url,
            "title": clean_text(item.get("title")),
            "source": clean_text(item.get("source")),
            "description": clean_text(item.get("description")) or clean_text(item.get("snippet")),
            "snippet": clean_text(item.get("snippet")),
            "image_url": clean_text(item.get("image_url")),
            "language": clean_text(item.get("language")),
            "published_at": published_at,
            "relevance_score": final_score,
        }

    def _store_articles(self, records: List[Dict[str, Any]]) -> int:
        if not records:
            return 0

        filtered = [{k: v for k, v in r.items() if k in self.article_cols} for r in records]
        filtered = [r for r in filtered if r.get("ticker") and r.get("url")]

        if not filtered:
            return 0

        with self.engine.begin() as conn:
            stmt = insert(self.stock_news_articles).values(filtered)
            stmt = stmt.on_conflict_do_update(
                index_elements=["ticker", "url"],
                set_={
                    "title": stmt.excluded.title,
                    "source": stmt.excluded.source,
                    "description": stmt.excluded.description,
                    "snippet": stmt.excluded.snippet,
                    "image_url": stmt.excluded.image_url,
                    "language": stmt.excluded.language,
                    "published_at": stmt.excluded.published_at,
                    "relevance_score": stmt.excluded.relevance_score,
                },
            )
            result = conn.execute(stmt)
            return result.rowcount or 0

    def ingest_recent_news(
        self,
        tickers: Optional[List[str]] = None,
        lookback_hours: int = 48,
        overlap_minutes: int = 30,
        max_pages_per_ticker: int = 3,
        api_limit_per_page: int = 3,
        flush_batch_size: int = 100,
        language: str = "en",
    ) -> None:
        if tickers is None:
            tickers = self.resolve_target_tickers()

        tickers = [t.strip().upper() for t in tickers if t and t.strip()]
        tickers = dedupe_keep_order(tickers)

        if not tickers:
            logger.warning("No tickers provided. Nothing to ingest.")
            return

        logger.info(
            f"STOCK-NEWS-INGEST start tickers={len(tickers)} "
            f"tickers={tickers} "
            f"lookback_hours={lookback_hours} "
            f"max_pages_per_ticker={max_pages_per_ticker} "
            f"api_limit_per_page={api_limit_per_page}"
        )

        buffer: List[Dict[str, Any]] = []

        requests_made = 0
        total_articles_seen = 0
        total_articles_written = 0
        skipped_missing = 0
        skipped_bad = 0

        def flush() -> None:
            nonlocal total_articles_written, buffer
            if not buffer:
                return

            written = self._store_articles(buffer)
            total_articles_written += written

            logger.info(f"[STOCK-NEWS-INGEST] flushed batch_size={len(buffer)} written={written}")
            buffer = []

        for idx, ticker in enumerate(tickers, start=1):
            published_before = utc_now()
            published_after = self.resolve_published_after(
                ticker=ticker,
                lookback_hours=lookback_hours,
                overlap_minutes=overlap_minutes,
            )

            logger.info(
                f"[STOCK-NEWS-INGEST] Processing {ticker} ({idx}/{len(tickers)}) "
                f"window={to_api_datetime(published_after)} -> {to_api_datetime(published_before)}"
            )

            for page in range(1, max_pages_per_ticker + 1):
                payload = self.fetch_news_page(
                    symbol=ticker,
                    published_after=published_after,
                    published_before=published_before,
                    page=page,
                    limit=api_limit_per_page,
                    language=language,
                )
                requests_made += 1

                items = payload.get("data") or []
                meta = payload.get("meta") or {}
                returned = int(meta.get("returned") or len(items) or 0)
                found = meta.get("found")

                logger.info(
                    f"[STOCK-NEWS-INGEST] ticker={ticker} page={page} returned={returned} found={found}"
                )

                if not items:
                    break

                for item in items:
                    total_articles_seen += 1

                    record = self.normalize_article(ticker, item)
                    if record is None:
                        if not item.get("url"):
                            skipped_missing += 1
                        else:
                            skipped_bad += 1
                        continue

                    buffer.append(record)

                    if len(buffer) >= flush_batch_size:
                        flush()

                if returned < api_limit_per_page:
                    break

        flush()

        logger.info(
            f"[STOCK-NEWS-INGEST] DONE "
            f"requests={requests_made} "
            f"seen={total_articles_seen} "
            f"written={total_articles_written} "
            f"skipped_missing={skipped_missing} "
            f"skipped_bad={skipped_bad}"
        )


if __name__ == "__main__":
    ing = StockNewsIngestor()
    ing.ingest_recent_news()
