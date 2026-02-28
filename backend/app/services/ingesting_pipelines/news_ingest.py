from __future__ import annotations

import os
import sys
import json
import logging
from datetime import datetime, timezone
from collections import defaultdict, Counter
from typing import Any, Dict, List, Optional, Tuple

from datasets import load_dataset, interleave_datasets
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

def get_hf_token_optional() -> Optional[str]:
    """
    Token is optional. If your dataset is private/gated, set HF_TOKEN or HUGGINGFACE_HUB_TOKEN.
    If it's public, this returns None and load_dataset will still work.
    """
    token = (os.getenv("HUGGINGFACE_HUB_TOKEN") or os.getenv("HF_TOKEN") or "").strip()
    return token or None


def parse_extras_any(extra_fields: Any) -> dict:
    """
    extra_fields in this dataset is often:
      - dict
      - JSON string
      - None
    Keep this cheap and safe.
    """
    if not extra_fields:
        return {}
    if isinstance(extra_fields, dict):
        return extra_fields
    if isinstance(extra_fields, str):
        s = extra_fields.strip()
        # quick reject: not JSON-like
        if not s or (s[0] not in "{["):
            return {}
        try:
            v = json.loads(s)
            return v if isinstance(v, dict) else {}
        except Exception:
            return {}
    return {}


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
# Date extraction
# ---------------------------

DATE_KEYS = ["date", "published_at", "publishedAt", "published", "datetime", "time", "timestamp"]

EXTRA_DATE_KEYS = ["date", "published_at", "publishedAt", "published", "published_time", "pub_date", "created_at"]


def pick_raw_date(row: Dict[str, Any]) -> Any:
    # 1) direct keys
    for k in DATE_KEYS:
        v = row.get(k)
        if v:
            return v

    # 2) try inside extra_fields (only if we must)
    extras = parse_extras_any(row.get("extra_fields"))
    for k in EXTRA_DATE_KEYS:
        v = extras.get(k)
        if v:
            return v

    return None


def safe_date_prefix(raw_date: Any) -> str:
    # We only need YYYY-MM-DD for window check
    s = str(raw_date or "").strip()
    return s[:10] if len(s) >= 10 else ""


def fast_parse_datetime_utc(raw_date: Any) -> Optional[datetime]:
    """
    Faster than pandas.to_datetime per row.
    Supports:
      - ISO8601 strings (with 'Z' or offset)
      - 'YYYY-MM-DD'
      - epoch seconds/millis (int/float)
    Returns tz-aware datetime in UTC.
    """
    if raw_date is None:
        return None

    # epoch
    if isinstance(raw_date, (int, float)):
        try:
            x = float(raw_date)
            # heuristic: millis if huge
            if x > 1e12:
                x = x / 1000.0
            return datetime.fromtimestamp(x, tz=timezone.utc)
        except Exception:
            return None

    s = str(raw_date).strip()
    if not s:
        return None

    # YYYY-MM-DD
    if len(s) >= 10 and s[4] == "-" and s[7] == "-" and (len(s) == 10 or s[10] in ("T", " ")):
        # ISO-ish
        try:
            # normalize Z
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            # allow space instead of T
            if len(s) > 10 and s[10] == " ":
                s = s[:10] + "T" + s[11:]
            dt = datetime.fromisoformat(s if "T" in s else s[:10])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            return dt
        except Exception:
            return None

    # last resort
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

        required = {"url", "published_at"}
        missing = [c for c in required if c not in self.article_cols]
        if missing:
            raise RuntimeError(f"'articles' table missing required columns: {missing}")

    def load_dataset_any(self, streaming: bool):
        token = get_hf_token_optional()
        # Load specific sub-dataset configs instead of the full combined dataset.
        # The full combined load (no name= arg) triggers a 20-min pre-processing
        # phase and can download ~90GB to Colab/production disk.
        # These configs are all financial-domain and cover 2020-2024.
        configs = [
            "sp500_daily_headlines",       # S&P 500 headlines 2008-2024
            "yahoo_finance_articles",       # Yahoo Finance 2025
            "yahoo_finance_felixdrinkall",  # Yahoo Finance 2017-2023
            "cnbc_headlines",               # CNBC financial news 2017-2020
        ]
        datasets_list = [
            load_dataset(
                "Brianferrell787/financial-news-multisource",
                name=cfg,
                split="train",
                streaming=streaming,
                token=token,
            )
            for cfg in configs
        ]
        if len(datasets_list) == 1:
            return datasets_list[0]
        return interleave_datasets(datasets_list)

    def _store_articles(self, records: List[Dict[str, Any]]) -> None:
        if not records:
            return

        # only columns that exist
        filtered = [{k: v for k, v in r.items() if k in self.article_cols} for r in records]
        filtered = [r for r in filtered if r]
        if not filtered:
            return

        with self.engine.begin() as conn:
            stmt = insert(self.articles).values(filtered)
            stmt = stmt.on_conflict_do_nothing(index_elements=["url"])  # UNIQUE(url)
            conn.execute(stmt)

    def ingest_all_years_one_pass(
        self,
        years: List[int],
        per_year: int = 1000,
        end_date: str = "2024-12-01",
        max_scanned: int = 5_000_000,  # lower default; 200M is brutal
        max_desc_chars: int = 280,
        flush_batch_size: int = 2000,   # fewer DB round-trips
        progress_every: int = 200_000,
        streaming: bool = True,
        fallback_to_non_streaming_after: int = 1_000_000,
        fallback_if_target_year_share_below: float = 0.0005,  # 0.05% of rows
        min_rows_for_share_check: int = 2_000_000,
    ) -> None:
        years_set = set(years)
        if not years_set:
            raise ValueError("years list is empty")

        end_year = int(end_date[:4])
        end_day = end_date[:10]

        accepted_per_year = defaultdict(int)
        year_seen = Counter()
        target_year_seen = 0

        def all_done() -> bool:
            return all(accepted_per_year[y] >= per_year for y in years_set)

        logger.info(
            f"INGEST-ALL one-pass years={sorted(years_set)} per_year={per_year} end_date={end_date} "
            f"flush_batch_size={flush_batch_size} streaming={streaming}"
        )

        ds = self.load_dataset_any(streaming=streaming)

        scanned = 0
        in_window = 0
        accepted = 0
        missing_url = 0
        bad_date = 0
        missing_date = 0

        buffer: List[Dict[str, Any]] = []
        buffer_urls = set()

        def flush():
            nonlocal buffer, buffer_urls
            if buffer:
                self._store_articles(buffer)
                buffer.clear()
                buffer_urls.clear()

        def log_progress():
            preview = " ".join([f"{y}:{accepted_per_year[y]}/{per_year}" for y in sorted(years_set)])
            top_years = ", ".join([f"{y}:{c}" for y, c in year_seen.most_common(5)])
            share = (target_year_seen / scanned) if scanned else 0.0
            logger.info(
                f"[INGEST-ALL] scanned={scanned:,} in_window={in_window:,} accepted={accepted:,} "
                f"missing_date={missing_date:,} missing_url={missing_url:,} bad_date={bad_date:,} "
                f"target_year_share={share:.6f} per_year={preview} top_years={top_years}"
            )

        for row in ds:
            scanned += 1

            if scanned == 1:
                try:
                    logger.info(f"DEBUG keys={list(row.keys())}")
                    logger.info(
                        f"DEBUG sample_row_date_fields: date={row.get('date')!r} published_at={row.get('published_at')!r}"
                    )
                except Exception:
                    pass

            if scanned % progress_every == 0:
                log_progress()

            if scanned >= max_scanned:
                logger.warning(f"[INGEST-ALL] Reached max_scanned={max_scanned:,}; stopping early.")
                break

            raw_date = pick_raw_date(row)
            if not raw_date:
                missing_date += 1
                continue

            date_prefix = safe_date_prefix(raw_date)
            if not date_prefix:
                bad_date += 1
                continue

            # stats
            try:
                y_str = date_prefix[:4]
                year_seen[y_str] += 1
                y = int(y_str)
            except Exception:
                bad_date += 1
                continue

            if y in years_set:
                target_year_seen += 1

            # fallback checks (avoid infinite scans in streaming)
            if streaming and scanned >= fallback_to_non_streaming_after and in_window == 0:
                logger.warning(
                    f"[INGEST-ALL] scanned={scanned:,} but still in_window=0 for years={sorted(years_set)}. "
                    f"Switching to non-streaming."
                )
                flush()
                return self.ingest_all_years_one_pass(
                    years=years,
                    per_year=per_year,
                    end_date=end_date,
                    max_scanned=max_scanned,
                    max_desc_chars=max_desc_chars,
                    flush_batch_size=flush_batch_size,
                    progress_every=progress_every,
                    streaming=False,
                    fallback_to_non_streaming_after=fallback_to_non_streaming_after,
                    fallback_if_target_year_share_below=fallback_if_target_year_share_below,
                    min_rows_for_share_check=min_rows_for_share_check,
                )

            if streaming and scanned >= min_rows_for_share_check:
                share = target_year_seen / scanned
                if share < fallback_if_target_year_share_below and in_window < 50:
                    logger.warning(
                        f"[INGEST-ALL] After scanned={scanned:,}, target_year_share={share:.6f} is very low "
                        f"and in_window={in_window}. Stream ordering likely unhelpful. Switching to non-streaming."
                    )
                    flush()
                    return self.ingest_all_years_one_pass(
                        years=years,
                        per_year=per_year,
                        end_date=end_date,
                        max_scanned=max_scanned,
                        max_desc_chars=max_desc_chars,
                        flush_batch_size=flush_batch_size,
                        progress_every=progress_every,
                        streaming=False,
                        fallback_to_non_streaming_after=fallback_to_non_streaming_after,
                        fallback_if_target_year_share_below=fallback_if_target_year_share_below,
                        min_rows_for_share_check=min_rows_for_share_check,
                    )

            # window check (cheap)
            if y not in years_set:
                continue
            if y == end_year and date_prefix > end_day:
                continue

            in_window += 1

            # quota check
            if accepted_per_year[y] >= per_year:
                if all_done():
                    logger.info(f"[INGEST-ALL] Quotas met. accepted={accepted:,} scanned={scanned:,}. Stopping.")
                    break
                continue

            # Parse extras only when row passes window/quota
            extras = parse_extras_any(row.get("extra_fields"))
            url = pick_url(extras)
            if not url:
                missing_url += 1
                continue

            # avoid duplicates inside the batch (saves DB conflict checks)
            if url in buffer_urls:
                continue

            ts = fast_parse_datetime_utc(raw_date)
            if ts is None:
                bad_date += 1
                continue

            title, desc = extract_title_and_desc(row.get("text", "") or "", max_desc_chars=max_desc_chars)
            source = pick_source(extras)

            record = {
                "url": url,
                "title": title or None,
                "description": desc or None,
                "published_at": ts,
                "source": source or None,
            }

            buffer.append(record)
            buffer_urls.add(url)
            accepted_per_year[y] += 1
            accepted += 1

            if len(buffer) >= flush_batch_size:
                flush()

            if all_done():
                logger.info(f"[INGEST-ALL] Quotas met. accepted={accepted:,} scanned={scanned:,}. Stopping.")
                break

        flush()
        log_progress()
        logger.info("[INGEST-ALL] DONE.")

        short = [(y, accepted_per_year[y]) for y in sorted(years_set) if accepted_per_year[y] < per_year]
        if short:
            logger.warning("[INGEST-ALL] SHORTFALLS:")
            for y, c in short:
                logger.warning(f"  {y}: {c}/{per_year}")


if __name__ == "__main__":
    ing = ArticleIngestor()

    years = [2019, 2020, 2021, 2022, 2023]
    end_date = "2023-12-31"

    ing.ingest_all_years_one_pass(
        years=years,
        per_year=1000,
        end_date=end_date,
        max_scanned=50_000_000,
        flush_batch_size=2000,
        progress_every=200_000,
        streaming=True,
        fallback_to_non_streaming_after=1_000_000,
    )