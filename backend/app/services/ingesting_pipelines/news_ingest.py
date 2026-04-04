from __future__ import annotations

import os
import sys
import json
import logging
from datetime import datetime, timezone, date
from collections import defaultdict, Counter
from typing import Any, Dict, List, Optional, Tuple

from datasets import load_dataset
from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.dialects.postgresql import insert

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger("article_ingestor")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

DEFAULT_HF_FILTERED_SUBSETS = [
    "yahoo_finance_felixdrinkall",
    "reddit_finance_sp500",
    "nyt_articles_2000_present",
    "american_news_jonasbecker",
    "cnbc_headlines",
    "benzinga_6000stocks",
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


def get_hf_token_optional() -> Optional[str]:
    token = (os.getenv("HUGGINGFACE_HUB_TOKEN") or os.getenv("HF_TOKEN") or "").strip()
    return token or None


def parse_extras_any(extra_fields: Any) -> dict:
    if not extra_fields:
        return {}
    if isinstance(extra_fields, dict):
        return extra_fields
    if isinstance(extra_fields, str):
        s = extra_fields.strip()
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


DATE_KEYS = ["date", "published_at", "publishedAt", "published", "datetime", "time", "timestamp"]
EXTRA_DATE_KEYS = ["date", "published_at", "publishedAt", "published", "published_time", "pub_date", "created_at"]


def pick_raw_date(row: Dict[str, Any]) -> Any:
    for k in DATE_KEYS:
        v = row.get(k)
        if v:
            return v

    extras = parse_extras_any(row.get("extra_fields"))
    for k in EXTRA_DATE_KEYS:
        v = extras.get(k)
        if v:
            return v

    return None


def safe_date_prefix(raw_date: Any) -> str:
    s = str(raw_date or "").strip()
    return s[:10] if len(s) >= 10 else ""


def fast_parse_datetime_utc(raw_date: Any) -> Optional[datetime]:
    if raw_date is None:
        return None

    if isinstance(raw_date, (int, float)):
        try:
            x = float(raw_date)
            if x > 1e12:
                x = x / 1000.0
            return datetime.fromtimestamp(x, tz=timezone.utc)
        except Exception:
            return None

    s = str(raw_date).strip()
    if not s:
        return None

    if len(s) >= 10 and s[4] == "-" and s[7] == "-" and (len(s) == 10 or s[10] in ("T", " ")):
        try:
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
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


def _resolve_years() -> List[int]:
    raw = (os.getenv("NEWS_INGEST_YEARS") or "").strip()
    if raw:
        out = []
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                out.append(int(part))
            except Exception:
                continue
        if out:
            return sorted(dict.fromkeys(out))

    start_year = int(os.getenv("NEWS_INGEST_START_YEAR", "2020"))
    current_year = date.today().year
    return list(range(start_year, current_year + 1))


def _resolve_end_date() -> str:
    return (os.getenv("NEWS_INGEST_END_DATE") or date.today().isoformat()).strip()


def _resolve_hf_subset_names() -> List[str]:
    raw = (os.getenv("NEWS_INGEST_HF_SUBSETS") or "").strip()
    if raw:
        names = [p.strip() for p in raw.split(",") if p.strip()]
        if names:
            return list(dict.fromkeys(names))
    return DEFAULT_HF_FILTERED_SUBSETS.copy()


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

    def load_dataset_any(self, streaming: bool, name: Optional[str] = None):
        token = get_hf_token_optional()
        if name:
            data_files = f"hf://datasets/Brianferrell787/financial-news-multisource/data/{name}/*.parquet"
            return load_dataset(
                "parquet",
                data_files=data_files,
                split="train",
                streaming=streaming,
                token=token,
            )
        return load_dataset(
            "Brianferrell787/financial-news-multisource",
            split="train",
            streaming=streaming,
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
            stmt = stmt.on_conflict_do_nothing(index_elements=["url"])
            conn.execute(stmt)

    def ingest_all_years_one_pass(
        self,
        years: List[int],
        per_year: int = 1000,
        end_date: Optional[str] = None,
        max_scanned: int = 50_000_000,
        max_desc_chars: int = 280,
        flush_batch_size: int = 2000,
        progress_every: int = 200_000,
        streaming: bool = True,
        fallback_to_non_streaming_after: int = 1_000_000,
        fallback_if_target_year_share_below: float = 0.0005,
        min_rows_for_share_check: int = 2_000_000,
        name: Optional[str] = None,
    ) -> None:
        if not end_date:
            end_date = date.today().isoformat()

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
            f"INGEST-ALL one-pass subset={name or 'ALL'} years={sorted(years_set)} "
            f"per_year={per_year} end_date={end_date} "
            f"flush_batch_size={flush_batch_size} streaming={streaming}"
        )

        ds = self.load_dataset_any(streaming=streaming, name=name)

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

            try:
                y_str = date_prefix[:4]
                year_seen[y_str] += 1
                y = int(y_str)
            except Exception:
                bad_date += 1
                continue

            if y in years_set:
                target_year_seen += 1

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
                    name=name,
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
                        name=name,
                    )

            if y not in years_set:
                continue
            if y == end_year and date_prefix > end_day:
                continue

            in_window += 1

            if accepted_per_year[y] >= per_year:
                if all_done():
                    logger.info(f"[INGEST-ALL] Quotas met. accepted={accepted:,} scanned={scanned:,}. Stopping.")
                    break
                continue

            extras = parse_extras_any(row.get("extra_fields"))
            url = pick_url(extras)
            if not url:
                missing_url += 1
                continue

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

    def ingest_filtered_subsets(
        self,
        subset_names: List[str],
        years: List[int],
        per_year: int = 1000,
        end_date: Optional[str] = None,
        max_scanned: int = 50_000_000,
        max_desc_chars: int = 280,
        flush_batch_size: int = 2000,
        progress_every: int = 200_000,
        streaming: bool = False,
    ) -> None:
        subset_names = [s.strip() for s in subset_names if s and s.strip()]
        subset_names = list(dict.fromkeys(subset_names))
        if not subset_names:
            raise ValueError("No subset names provided for filtered HF ingest.")

        logger.info("Running filtered HF ingest for subsets=%s", subset_names)

        for subset_name in subset_names:
            logger.info("Starting subset ingest: %s", subset_name)
            self.ingest_all_years_one_pass(
                years=years,
                per_year=per_year,
                end_date=end_date,
                max_scanned=max_scanned,
                max_desc_chars=max_desc_chars,
                flush_batch_size=flush_batch_size,
                progress_every=progress_every,
                streaming=streaming,
                fallback_to_non_streaming_after=1_000_000,
                name=subset_name,
            )
            logger.info("Finished subset ingest: %s", subset_name)


def run_hf_news_ingest_from_env(db_url: Optional[str] = None) -> None:
    ing = ArticleIngestor(db_url)
    years = _resolve_years()
    end_date = _resolve_end_date()
    per_year = int(os.getenv("NEWS_INGEST_PER_YEAR", "1000"))
    max_scanned = int(os.getenv("NEWS_INGEST_MAX_SCANNED", "50000000"))
    flush_batch_size = int(os.getenv("NEWS_INGEST_FLUSH_BATCH_SIZE", "2000"))
    progress_every = int(os.getenv("NEWS_INGEST_PROGRESS_EVERY", "200000"))
    streaming = os.getenv("NEWS_INGEST_STREAMING", "0").strip().lower() in {"1", "true", "yes", "y", "on"}
    filtered_mode = os.getenv("NEWS_INGEST_FILTERED_MODE", "1").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }

    if filtered_mode:
        subset_names = _resolve_hf_subset_names()
        ing.ingest_filtered_subsets(
            subset_names=subset_names,
            years=years,
            per_year=per_year,
            end_date=end_date,
            max_scanned=max_scanned,
            flush_batch_size=flush_batch_size,
            progress_every=progress_every,
            streaming=streaming,
        )
        return

    ing.ingest_all_years_one_pass(
        years=years,
        per_year=per_year,
        end_date=end_date,
        max_scanned=max_scanned,
        flush_batch_size=flush_batch_size,
        progress_every=progress_every,
        streaming=streaming,
        fallback_to_non_streaming_after=1_000_000,
    )


if __name__ == "__main__":
    run_hf_news_ingest_from_env()
