
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline as hf_pipeline

from sqlalchemy import create_engine, MetaData, Table, select, and_, text
from sqlalchemy.dialects.postgresql import insert


logger = logging.getLogger("finbert_pipeline")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)

DEFAULT_TOTAL_TO_PROCESS = 5000
DEFAULT_FETCH_BATCH = 500
DEFAULT_FINBERT_BATCH = 8
DEFAULT_DB_BATCH = 250
DEFAULT_TABLES = "articles,stock_news_articles"

_FINBERT_MODEL_ID = "ProsusAI/finbert"


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


def reflect_table(engine, table_name: str) -> Tuple[Table, List[str]]:
    metadata = MetaData()
    metadata.reflect(engine, only=[table_name])
    if table_name not in metadata.tables:
        raise RuntimeError(f"Table '{table_name}' does not exist in the database.")
    tbl = metadata.tables[table_name]
    return tbl, list(tbl.c.keys())


def ensure_sentiment_columns(engine, table_name: str) -> Tuple[Table, List[str]]:
    desired = {
        "sentiment": "TEXT",
        "sentiment_score": "DOUBLE PRECISION",
        "prob_pos": "DOUBLE PRECISION",
        "prob_neg": "DOUBLE PRECISION",
        "prob_neu": "DOUBLE PRECISION",
    }
    with engine.begin() as conn:
        for col, sql_type in desired.items():
            conn.execute(text(f'ALTER TABLE "{table_name}" ADD COLUMN IF NOT EXISTS {col} {sql_type};'))
    return reflect_table(engine, table_name)


def resolve_table_window(
    engine,
    table: Table,
    start_date: Optional[str],
    end_date: Optional[str],
) -> Tuple[str, str]:
    if start_date and end_date:
        return start_date, end_date

    stmt = select(
        text("MIN(published_at) AS min_published_at"),
        text("MAX(published_at) AS max_published_at"),
    ).select_from(table).where(table.c.published_at.is_not(None))

    with engine.connect() as conn:
        row = conn.execute(stmt).mappings().first()

    min_dt = row["min_published_at"] if row else None
    max_dt = row["max_published_at"] if row else None

    if min_dt is None or max_dt is None:
        raise RuntimeError(f"Could not determine date window for table '{table.name}' because published_at is empty.")

    if start_date:
        start = start_date
    else:
        start = pd.to_datetime(min_dt, utc=True).strftime("%Y-%m-%d")

    if end_date:
        end = end_date
    else:
        end = pd.to_datetime(max_dt, utc=True).strftime("%Y-%m-%d")

    return start, end


def select_device() -> int:
    force_cpu = os.getenv("FINBERT_FORCE_CPU", "").strip().lower() in {"1", "true", "yes"}
    if force_cpu:
        return -1

    try:
        import torch
    except Exception as e:
        logger.warning(f"Torch import failed; using CPU. error={e!r}")
        return -1

    if not getattr(torch, "cuda", None) or not torch.cuda.is_available():
        return -1

    try:
        _ = torch.zeros(1, device="cuda")
        return 0
    except Exception as e:
        logger.warning(f"CUDA appears unavailable at runtime; using CPU. error={e!r}")
        return -1


def _is_cuda_related_error(exc: BaseException) -> bool:
    msg = (str(exc) or "").lower()
    return any(
        k in msg
        for k in (
            "cuda",
            "cudnn",
            "cublas",
            "device-side assert",
            "out of memory",
            "not compiled with cuda",
            "no kernel image is available",
        )
    )


def _clear_finbert_pipeline_cache() -> None:
    if hasattr(get_finbert_pipeline, "finbert"):
        delattr(get_finbert_pipeline, "finbert")


def get_finbert_pipeline(*, force_cpu: bool = False):
    if not hasattr(get_finbert_pipeline, "finbert"):
        requested_device_id = -1 if force_cpu else select_device()

        def _build(device_id: int):
            logger.info(f"Loading FinBERT model (device_id={device_id})...")
            if device_id != -1:
                try:
                    import torch
                    model = AutoModelForSequenceClassification.from_pretrained(
                        _FINBERT_MODEL_ID,
                        dtype=torch.float16,
                    )
                except Exception:
                    model = AutoModelForSequenceClassification.from_pretrained(_FINBERT_MODEL_ID)
            else:
                model = AutoModelForSequenceClassification.from_pretrained(_FINBERT_MODEL_ID)

            tokenizer = AutoTokenizer.from_pretrained(_FINBERT_MODEL_ID)
            return hf_pipeline(
                task="sentiment-analysis",
                model=model,
                tokenizer=tokenizer,
                device=device_id,
                top_k=None,
                truncation=True,
                max_length=512,
            )

        try:
            get_finbert_pipeline.finbert = _build(requested_device_id)
            logger.info(f"FinBERT model loaded on device_id={requested_device_id}")
        except Exception as e:
            if requested_device_id != -1 and _is_cuda_related_error(e):
                logger.warning(f"FinBERT CUDA init failed; retrying on CPU. error={e!r}")
                get_finbert_pipeline.finbert = _build(-1)
                logger.info("FinBERT model loaded on device_id=-1")
            else:
                raise

    return get_finbert_pipeline.finbert


class FetchFromDBArtifact(BaseModel):
    table_name: str
    limit: int
    start_date: str
    end_date: str
    only_missing_sentiment: bool = True


class IngestArtifact(BaseModel):
    table_name: str
    published_at: List[str]
    title: List[str]
    description: List[str]
    url: List[str]
    source: List[str]
    ticker: List[str]


class SentimentArtifact(IngestArtifact):
    sentiment: List[str]
    sentiment_score: List[float]
    prob_pos: List[float]
    prob_neg: List[float]
    prob_neu: List[float]


def _compose_text_for_finbert(title: str, description: str) -> str:
    title = (title or "").strip()
    description = (description or "").strip()
    if title and description:
        return f"{title}. {description}"
    return title or description


def _scores_dict(all_scores: List[Dict[str, float]]) -> Dict[str, float]:
    d = {e["label"].lower(): float(e["score"]) for e in all_scores}
    for k in ("positive", "neutral", "negative"):
        d.setdefault(k, 0.0)
    return d


def fetch_articles_from_db(engine, table: Table, cols: set, artifact: FetchFromDBArtifact) -> IngestArtifact:
    where_clauses = []

    if artifact.only_missing_sentiment and "sentiment" in cols:
        where_clauses.append(table.c.sentiment.is_(None))

    start_dt = pd.to_datetime(artifact.start_date, utc=True, errors="raise")
    end_dt = pd.to_datetime(artifact.end_date, utc=True, errors="raise")

    where_clauses.append(table.c.published_at >= start_dt.to_pydatetime())
    # inclusive end date at 23:59:59
    end_dt = end_dt + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
    where_clauses.append(table.c.published_at <= end_dt.to_pydatetime())

    select_cols = [table.c.published_at, table.c.url]
    if "ticker" in cols:
        select_cols.append(table.c.ticker)
    if "title" in cols:
        select_cols.append(table.c.title)
    if "description" in cols:
        select_cols.append(table.c.description)
    elif "snippet" in cols:
        select_cols.append(table.c.snippet)
    if "source" in cols:
        select_cols.append(table.c.source)

    stmt = (
        select(*select_cols)
        .where(and_(*where_clauses))
        .order_by(table.c.published_at.desc())
        .limit(int(artifact.limit))
    )

    logger.info(
        "[FetchFromDB] table=%s limit=%s start=%s end=%s only_missing=%s",
        artifact.table_name,
        artifact.limit,
        artifact.start_date,
        artifact.end_date,
        artifact.only_missing_sentiment,
    )

    with engine.connect() as conn:
        rows = conn.execute(stmt).fetchall()

    if not rows:
        return IngestArtifact(
            table_name=artifact.table_name,
            published_at=[],
            title=[],
            description=[],
            url=[],
            source=[],
            ticker=[],
        )

    published_at_list: List[str] = []
    title_list: List[str] = []
    desc_list: List[str] = []
    url_list: List[str] = []
    source_list: List[str] = []
    ticker_list: List[str] = []

    for r in rows:
        published_at = r[0]
        url = r[1]
        idx = 2

        ticker = ""
        title = ""
        description = ""
        source = ""

        if "ticker" in cols:
            ticker = r[idx] if idx < len(r) else ""
            idx += 1
        if "title" in cols:
            title = r[idx] if idx < len(r) else ""
            idx += 1
        if "description" in cols or "snippet" in cols:
            description = r[idx] if idx < len(r) else ""
            idx += 1
        if "source" in cols:
            source = r[idx] if idx < len(r) else ""
            idx += 1

        if not url:
            continue

        dt = pd.to_datetime(published_at, utc=True, errors="coerce")
        if pd.isna(dt):
            continue

        published_at_list.append(dt.strftime("%Y-%m-%dT%H:%M:%SZ"))
        url_list.append(str(url).strip())
        ticker_list.append((ticker or "").strip())
        title_list.append((title or "").strip())
        desc_list.append((description or "").strip())
        source_list.append((source or "").strip())

    return IngestArtifact(
        table_name=artifact.table_name,
        published_at=published_at_list,
        title=title_list,
        description=desc_list,
        url=url_list,
        source=source_list,
        ticker=ticker_list,
    )


def finbert_score(artifact: IngestArtifact) -> SentimentArtifact:
    if not artifact.url:
        return SentimentArtifact(
            table_name=artifact.table_name,
            published_at=[],
            title=[],
            description=[],
            url=[],
            source=[],
            ticker=[],
            sentiment=[],
            sentiment_score=[],
            prob_pos=[],
            prob_neg=[],
            prob_neu=[],
        )

    inputs = [_compose_text_for_finbert(t, d) for t, d in zip(artifact.title, artifact.description)]

    if not any(x.strip() for x in inputs):
        n = len(inputs)
        return SentimentArtifact(
            table_name=artifact.table_name,
            published_at=artifact.published_at,
            title=artifact.title,
            description=artifact.description,
            url=artifact.url,
            source=artifact.source,
            ticker=artifact.ticker,
            sentiment=["neutral"] * n,
            sentiment_score=[0.0] * n,
            prob_pos=[0.0] * n,
            prob_neg=[0.0] * n,
            prob_neu=[1.0] * n,
        )

    pipe = get_finbert_pipeline()
    finbert_batch = int(os.getenv("FINBERT_BATCH_SIZE", str(DEFAULT_FINBERT_BATCH)))

    try:
        results = pipe(inputs, batch_size=finbert_batch)
    except Exception as e:
        if _is_cuda_related_error(e):
            logger.warning(f"FinBERT inference failed on CUDA; retrying on CPU. error={e!r}")
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
            _clear_finbert_pipeline_cache()
            pipe = get_finbert_pipeline(force_cpu=True)
            results = pipe(inputs, batch_size=finbert_batch)
        else:
            raise

    sentiments: List[str] = []
    scores: List[float] = []
    prob_pos: List[float] = []
    prob_neg: List[float] = []
    prob_neu: List[float] = []

    for result in results:
        score_map = _scores_dict(result)
        label = max(score_map, key=score_map.get)
        pos = score_map["positive"]
        neg = score_map["negative"]
        neu = score_map["neutral"]

        sentiments.append(label)
        scores.append(pos - neg)
        prob_pos.append(pos)
        prob_neg.append(neg)
        prob_neu.append(neu)

    return SentimentArtifact(
        table_name=artifact.table_name,
        published_at=artifact.published_at,
        title=artifact.title,
        description=artifact.description,
        url=artifact.url,
        source=artifact.source,
        ticker=artifact.ticker,
        sentiment=sentiments,
        sentiment_score=scores,
        prob_pos=prob_pos,
        prob_neg=prob_neg,
        prob_neu=prob_neu,
    )


def write_sentiment_to_db(engine, table: Table, cols: set, artifact: SentimentArtifact) -> int:
    n = len(artifact.url)
    if n == 0:
        return 0

    records: List[Dict[str, Any]] = []
    for i in range(n):
        url = artifact.url[i]
        if not url:
            continue

        dt = pd.to_datetime(artifact.published_at[i], utc=True, errors="coerce")
        if pd.isna(dt):
            continue

        rec: Dict[str, Any] = {"url": url}

        if "ticker" in cols:
            rec["ticker"] = artifact.ticker[i] or None
        if "published_at" in cols:
            rec["published_at"] = dt.to_pydatetime()
        if "title" in cols:
            rec["title"] = artifact.title[i] or None
        if "description" in cols:
            rec["description"] = artifact.description[i] or None
        elif "snippet" in cols:
            rec["snippet"] = artifact.description[i] or None
        if "source" in cols:
            rec["source"] = artifact.source[i] or None

        if "sentiment" in cols:
            rec["sentiment"] = artifact.sentiment[i] or None
        if "sentiment_score" in cols:
            rec["sentiment_score"] = float(artifact.sentiment_score[i]) if artifact.sentiment_score[i] is not None else None
        if "prob_pos" in cols:
            rec["prob_pos"] = float(artifact.prob_pos[i]) if artifact.prob_pos[i] is not None else None
        if "prob_neg" in cols:
            rec["prob_neg"] = float(artifact.prob_neg[i]) if artifact.prob_neg[i] is not None else None
        if "prob_neu" in cols:
            rec["prob_neu"] = float(artifact.prob_neu[i]) if artifact.prob_neu[i] is not None else None

        records.append(rec)

    if not records:
        return 0

    db_batch = int(os.getenv("FINBERT_DB_BATCH_SIZE", str(DEFAULT_DB_BATCH)))
    written = 0

    conflict_keys = ["url"]
    if table.name == "stock_news_articles" and "ticker" in cols:
        conflict_keys = ["ticker", "url"]

    for i in range(0, len(records), db_batch):
        batch = records[i: i + db_batch]
        with engine.begin() as conn:
            stmt = insert(table).values(batch)

            set_dict: Dict[str, Any] = {}
            for col_name in ("published_at", "title", "description", "snippet", "source", "sentiment", "sentiment_score", "prob_pos", "prob_neg", "prob_neu"):
                if col_name in cols:
                    set_dict[col_name] = getattr(stmt.excluded, col_name)

            stmt = stmt.on_conflict_do_update(
                index_elements=conflict_keys,
                set_=set_dict,
            )
            conn.execute(stmt)

        written += len(batch)
        logger.info(
            "[WriteSentimentToDB] table=%s processed=%s/%s",
            table.name,
            written,
            len(records),
        )

    return len(records)


def _parse_table_list(raw: str) -> List[str]:
    out: List[str] = []
    for item in raw.split(","):
        name = item.strip()
        if name:
            out.append(name)
    return out or ["articles"]


def run_finbert_pipeline_for_table(
    engine,
    table_name: str,
    start_date: Optional[str],
    end_date: Optional[str],
    total_target: int,
    fetch_batch: int,
    only_missing: bool,
) -> Dict[str, Any]:
    table, col_list = ensure_sentiment_columns(engine, table_name)
    cols = set(col_list)

    try:
        start_date_resolved, end_date_resolved = resolve_table_window(engine, table, start_date, end_date)
    except RuntimeError as e:
        logger.warning("%s Skipping table '%s'.", e, table_name)
        return {
            "table": table_name,
            "start_date": start_date,
            "end_date": end_date,
            "fetched": 0,
            "written": 0,
            "skipped": True,
        }

    logger.info(
        "FinBERT run starting: table=%s window=%s..%s total_target=%s fetch_batch=%s only_missing=%s",
        table_name, start_date_resolved, end_date_resolved, total_target, fetch_batch, only_missing
    )

    total_fetched = 0
    total_written = 0
    loops = 0

    while total_fetched < total_target:
        loops += 1
        remaining = total_target - total_fetched
        this_limit = min(fetch_batch, remaining)

        fetch_art = FetchFromDBArtifact(
            table_name=table_name,
            limit=this_limit,
            start_date=start_date_resolved,
            end_date=end_date_resolved,
            only_missing_sentiment=only_missing,
        )

        batch = fetch_articles_from_db(engine, table, cols, fetch_art)
        n = len(batch.url)

        if n == 0:
            logger.info("No more matching rows found for table '%s'. Stopping.", table_name)
            break

        logger.info(
            "[Loop %s][%s] fetched=%s (total_fetched would become %s/%s)",
            loops, table_name, n, total_fetched + n, total_target
        )

        scored = finbert_score(batch)
        written = write_sentiment_to_db(engine, table, cols, scored)

        total_fetched += n
        total_written += written

        logger.info("[Loop %s][%s] wrote=%s total_written=%s", loops, table_name, written, total_written)

        if n < this_limit:
            logger.info("Fetched fewer than requested in last batch for table '%s'; likely exhausted. Stopping.", table_name)
            break

    logger.info(
        "FinBERT run complete: table=%s total_fetched=%s total_written=%s window=%s..%s",
        table_name, total_fetched, total_written, start_date_resolved, end_date_resolved
    )

    return {
        "table": table_name,
        "start_date": start_date_resolved,
        "end_date": end_date_resolved,
        "fetched": total_fetched,
        "written": total_written,
        "skipped": False,
    }


def run_finbert_pipeline_from_env() -> Dict[str, Any]:
    db_url = build_db_url()
    engine = create_engine(db_url)

    start_date = os.getenv("FINBERT_START_DATE", "").strip() or None
    end_date = os.getenv("FINBERT_END_DATE", "").strip() or None
    total_target = int(os.getenv("FINBERT_TOTAL", str(DEFAULT_TOTAL_TO_PROCESS)))
    fetch_batch = int(os.getenv("FINBERT_FETCH_BATCH", str(DEFAULT_FETCH_BATCH)))
    only_missing = os.getenv("FINBERT_ONLY_MISSING", "true").strip().lower() in {"1", "true", "yes"}
    table_names = _parse_table_list(os.getenv("FINBERT_TABLES", DEFAULT_TABLES))

    results: List[Dict[str, Any]] = []
    for table_name in table_names:
        try:
            results.append(
                run_finbert_pipeline_for_table(
                    engine=engine,
                    table_name=table_name,
                    start_date=start_date,
                    end_date=end_date,
                    total_target=total_target,
                    fetch_batch=fetch_batch,
                    only_missing=only_missing,
                )
            )
        except Exception as exc:
            logger.exception("FinBERT run failed for table '%s': %s", table_name, exc)
            results.append(
                {
                    "table": table_name,
                    "start_date": start_date,
                    "end_date": end_date,
                    "fetched": 0,
                    "written": 0,
                    "skipped": True,
                    "error": str(exc),
                }
            )

    return {"tables": results}


if __name__ == "__main__":
    run_finbert_pipeline_from_env()
