from __future__ import annotations

import os
import sys
import json
import re
import logging
from collections import Counter
from typing import Dict, List, Optional, Tuple, Any, Set

import pandas as pd
from datasets import load_dataset
from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.dialects.postgresql import insert


# Optional: project root on path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger("article_ingestor")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


# ---------------------------
# DB helpers
# ---------------------------

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


# ---------------------------
# HF helpers
# ---------------------------

def get_hf_token() -> str:
    token = (os.getenv("HUGGINGFACE_HUB_TOKEN") or os.getenv("HF_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("Missing Hugging Face token. Set HF_TOKEN (or HUGGINGFACE_HUB_TOKEN) in .env.")
    return token


# ---------------------------
# Parsing helpers
# ---------------------------

def safe_date_prefix(date_val: Any) -> str:
    s = str(date_val or "")
    return s[:10] if len(s) >= 10 else ""


def parse_extras_any(extra_fields: Any) -> dict:
    """
    Dataset sometimes provides extra_fields as JSON string, sometimes as dict.
    Handle both.
    """
    if not extra_fields:
        return {}
    if isinstance(extra_fields, dict):
        return extra_fields
    if isinstance(extra_fields, str):
        try:
            return json.loads(extra_fields)
        except Exception:
            return {}
    return {}


def pick_stocks(extras: dict) -> List[str]:
    stocks = extras.get("stocks")
    if isinstance(stocks, list) and stocks:
        return [str(s).strip() for s in stocks if str(s).strip()]
    return []


def normalize_ticker(s: str) -> str:
    s = (s or "").strip().upper()
    if not s:
        return ""
    # Common patterns: "NYSE:KSS", "NASDAQ:AAPL"
    if ":" in s:
        s = s.split(":", 1)[1].strip()
    # drop indices
    if s.startswith("$"):
        return ""
    return s


def is_reasonable_ticker_looser(s: str) -> bool:
    s = normalize_ticker(s)
    if not s:
        return False
    # allow A-Z, digits, dot, dash; 1 to 10 chars, starts with letter
    return bool(re.fullmatch(r"[A-Z][A-Z0-9\.\-]{0,9}", s))


def extract_title_and_desc(text: str, max_desc_chars: int = 280) -> Tuple[str, str]:
    if not text:
        return "", ""
    parts = text.split("\n\n", 1)
    title = parts[0].strip()
    body = parts[1].strip() if len(parts) > 1 else ""
    desc = body[:max_desc_chars].strip()
    return title, desc


def pick_url(extras: Dict[str, Any]) -> Optional[str]:
    return extras.get("url") or extras.get("web_url") or extras.get("link") or extras.get("permalink")


def pick_source(extras: Dict[str, Any]) -> Optional[str]:
    return (
        extras.get("source")
        or extras.get("publisher")
        or extras.get("publication")
        or extras.get("source_norm")
        or extras.get("source_domain")
        or extras.get("news_outlet")
    )


# ---------------------------
# Core ingestor
# ---------------------------

class ArticleIngestor:
    def __init__(self, db_url: Optional[str] = None):
        if db_url is None:
            db_url = build_db_url()

        logger.info(f"Connecting to database at {db_url} ...")
        self.engine = create_engine(db_url)
        self.metadata = MetaData()

        logger.info("Reflecting 'articles' table from database...")
        self.metadata.reflect(self.engine, only=["articles"])
        if "articles" not in self.metadata.tables:
            raise RuntimeError("Table 'articles' does not exist in the database.")

        self.articles: Table = self.metadata.tables["articles"]
        self.article_cols = set(self.articles.c.keys())
        logger.info(f"Successfully reflected 'articles' table. columns={sorted(self.article_cols)}")

        required = {"url", "published_at", "stock"}
        missing = [c for c in required if c not in self.article_cols]
        if missing:
            raise RuntimeError(f"'articles' table missing required columns: {missing}")

    def load_stream_raw(self):
        token = get_hf_token()
        return load_dataset(
            "Brianferrell787/financial-news-multisource",
            split="train",
            streaming=True,
            token=token,
        )

    def _store_articles(self, records: List[Dict[str, Any]]) -> None:
        if not records:
            return

        filtered = [{k: v for k, v in r.items() if k in self.article_cols} for r in records]
        filtered = [r for r in filtered if r]
        if not filtered:
            return

        with self.engine.begin() as conn:
            stmt = insert(self.articles).values(filtered)
            # IMPORTANT: matches your DB constraint UNIQUE(url, stock)
            stmt = stmt.on_conflict_do_nothing(index_elements=["url", "stock"])
            conn.execute(stmt)

    # ---------------------------
    # Phase 1: Discover top tickers in-year-window (FCFS)
    # ---------------------------

    def discover_top_tickers_fcfs(
        self,
        years: List[int],
        end_date: str,
        top_k: int = 15,
        scan_limit: int = 25_000_000,
        progress_every: int = 500_000,
    ) -> List[str]:
        years_set = set(years)
        end_year = int(end_date[:4])
        end_day = end_date[:10]

        counts: Counter[str] = Counter()
        scanned = 0
        in_window = 0
        rows_with_stocks = 0

        ds = self.load_stream_raw()

        for row in ds:
            scanned += 1
            if scanned % progress_every == 0:
                top_preview = ", ".join([f"{t}:{c}" for t, c in counts.most_common(5)])
                logger.info(
                    f"[DISCOVER] scanned={scanned:,} in_window={in_window:,} rows_with_stocks={rows_with_stocks:,} "
                    f"unique_tickers={len(counts):,} top={top_preview}"
                )

            if scanned >= scan_limit:
                logger.warning(f"[DISCOVER] Reached scan_limit={scan_limit:,}; stopping discovery early.")
                break

            date_prefix = safe_date_prefix(row.get("date"))
            if not date_prefix:
                continue

            y = int(date_prefix[:4])
            if y not in years_set:
                continue
            if y == end_year and date_prefix > end_day:
                continue

            in_window += 1

            extras = parse_extras_any(row.get("extra_fields"))
            stocks = pick_stocks(extras)
            if not stocks:
                continue

            rows_with_stocks += 1

            # count each ticker at most once per row
            valid: Set[str] = set()
            for s in stocks:
                t = normalize_ticker(str(s))
                if is_reasonable_ticker_looser(t):
                    valid.add(t)

            for t in valid:
                counts[t] += 1

        top = [t for t, _ in counts.most_common(top_k)]
        logger.info(f"[DISCOVER] DONE. top{top_k}={top}")
        if not top:
            logger.warning(
                "[DISCOVER] No tickers discovered in the requested window. "
                "This usually means the stream order hasn't reached those years yet, or the dataset schema differs."
            )
        return top

    # ---------------------------
    # Phase 2: One-pass ingest for (year, ticker) quotas
    # ---------------------------

    def ingest_multi_year_one_pass(
        self,
        tickers: List[str],
        years: List[int],
        per_ticker_per_year: int = 500,
        end_date: str = "2024-12-01",
        max_scanned: int = 200_000_000,
        max_desc_chars: int = 280,
        flush_batch_size: int = 1000,
        progress_every: int = 200_000,
    ) -> None:
        tickers_set = {normalize_ticker(t) for t in tickers if normalize_ticker(t)}
        years_set = set(years)
        if not tickers_set:
            raise ValueError("tickers list is empty after normalization")
        if not years_set:
            raise ValueError("years list is empty")

        end_year = int(end_date[:4])
        end_day = end_date[:10]

        targets = {(y, t): per_ticker_per_year for y in years_set for t in tickers_set}
        counts = {(y, t): 0 for (y, t) in targets}

        def all_done() -> bool:
            return all(counts[k] >= targets[k] for k in targets)

        logger.info(
            f"ONE-PASS ingest years={sorted(years_set)} tickers={len(tickers_set)} "
            f"target_each={per_ticker_per_year} end_date={end_date}"
        )

        ds = self.load_stream_raw()

        scanned = 0
        accepted = 0
        in_window = 0
        rows_with_stocks = 0
        matched_any = 0

        buffer: List[Dict[str, Any]] = []

        sample_ticker = sorted(tickers_set)[0]

        for row in ds:
            scanned += 1
            if scanned % progress_every == 0:
                sample = ", ".join([f"{y}:{counts[(y, sample_ticker)]}/{per_ticker_per_year}" for y in sorted(years_set)])
                logger.info(
                    f"[INGEST] scanned={scanned:,} in_window={in_window:,} rows_with_stocks={rows_with_stocks:,} "
                    f"matched_any={matched_any:,} accepted={accepted:,} sample({sample_ticker})={sample}"
                )

            if scanned >= max_scanned:
                logger.warning(f"[INGEST] Reached max_scanned={max_scanned:,}; stopping early.")
                break

            date_prefix = safe_date_prefix(row.get("date"))
            if not date_prefix:
                continue

            y = int(date_prefix[:4])
            if y not in years_set:
                continue
            if y == end_year and date_prefix > end_day:
                continue

            in_window += 1

            extras = parse_extras_any(row.get("extra_fields"))
            stocks = pick_stocks(extras)
            if not stocks:
                continue

            rows_with_stocks += 1

            valid = {normalize_ticker(s) for s in stocks}
            match = [t for t in valid if t in tickers_set and is_reasonable_ticker_looser(t)]
            if not match:
                continue

            matched_any += 1

            chosen = None
            for t in sorted(match):
                if counts[(y, t)] < per_ticker_per_year:
                    chosen = t
                    break
            if not chosen:
                continue

            url = pick_url(extras)
            if not url:
                continue

            try:
                dt = pd.to_datetime(row.get("date"), utc=True, errors="raise").to_pydatetime()
            except Exception:
                continue

            title, desc = extract_title_and_desc(row.get("text", "") or "", max_desc_chars=max_desc_chars)
            source = pick_source(extras)

            record = {
                "url": url,
                "title": title or None,
                "description": desc or None,
                "published_at": dt,
                "stock": chosen,
                "source": source or None,
            }

            buffer.append(record)
            counts[(y, chosen)] += 1
            accepted += 1

            if len(buffer) >= flush_batch_size:
                self._store_articles(buffer)
                buffer.clear()

            if all_done():
                logger.info(f"[INGEST] Quotas met. accepted={accepted:,} scanned={scanned:,}. Stopping.")
                break

        if buffer:
            self._store_articles(buffer)
            buffer.clear()

        logger.info(
            f"[INGEST] DONE. accepted={accepted:,} scanned={scanned:,} in_window={in_window:,} "
            f"rows_with_stocks={rows_with_stocks:,} matched_any={matched_any:,}"
        )

        shortfalls = [(y, t, counts[(y, t)]) for (y, t) in targets if counts[(y, t)] < per_ticker_per_year]
        if shortfalls:
            logger.warning(f"[INGEST] SHORTFALLS: {len(shortfalls)} year-ticker slots did not reach target={per_ticker_per_year}. Showing up to 10:")
            for y, t, c in shortfalls[:10]:
                logger.warning(f"  {y} {t}: {c}/{per_ticker_per_year}")


if __name__ == "__main__":
    ing = ArticleIngestor()

    years = [2020, 2021, 2022, 2023, 2024]
    end_date = "2024-12-01"

    # Phase 1: FCFS discovery (find the densest tickers inside your 5-year window)
    top15 = ing.discover_top_tickers_fcfs(
        years=years,
        end_date=end_date,
        top_k=15,
        scan_limit=25_000_000,  # tune up if needed
        progress_every=500_000,
    )

    # Phase 2: fill 500 per ticker per year for those tickers
    if top15:
        ing.ingest_multi_year_one_pass(
            tickers=top15,
            years=years,
            per_ticker_per_year=500,
            end_date=end_date,
            max_scanned=200_000_000,
            flush_batch_size=1000,
            progress_every=200_000,
        )
    else:
        logger.error("No tickers discovered; skipping ingest. Increase scan_limit or confirm dataset contains the target years.")
