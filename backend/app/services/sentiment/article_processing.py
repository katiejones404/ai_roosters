from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline as hf_pipeline

from sqlalchemy import create_engine, MetaData, Table, select, and_
from sqlalchemy.dialects.postgresql import insert


# --------------------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------------------
logger = logging.getLogger("finbert_pipeline")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)


# --------------------------------------------------------------------------------------
# Defaults pinned to your price window (AMZN/NVDA):
# prices: 2019-01-02 -> 2024-07-30
# --------------------------------------------------------------------------------------
DEFAULT_START_DATE = "2019-01-02"
DEFAULT_END_DATE = "2024-07-30"

# Total number of articles to process in one run (looped batches)
DEFAULT_TOTAL_TO_PROCESS = 5000

# Fetch batch size per DB query (keep this moderate for RAM/CPU)
DEFAULT_FETCH_BATCH = 500

# FinBERT inference batch size (HF pipeline batching)
DEFAULT_FINBERT_BATCH = 8

# DB write batch size
DEFAULT_DB_BATCH = 250

_FINBERT_MODEL_ID = "ProsusAI/finbert"


# --------------------------------------------------------------------------------------
# DB helpers
# --------------------------------------------------------------------------------------
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


def get_articles_table(engine) -> Tuple[Table, List[str]]:
    """
    Reflect articles table and return (table, column_names).
    """
    metadata = MetaData()
    metadata.reflect(engine, only=["articles"])
    if "articles" not in metadata.tables:
        raise RuntimeError("Table 'articles' does not exist in the database.")
    tbl = metadata.tables["articles"]
    return tbl, list(tbl.c.keys())


# --------------------------------------------------------------------------------------
# Device selection (prefer CUDA; fallback to CPU)
# --------------------------------------------------------------------------------------
def select_device() -> int:
    """Return HF pipeline device id: 0 for CUDA:0, -1 for CPU."""
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
    """
    Cached HF pipeline instance.
    """
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


# --------------------------------------------------------------------------------------
# Artifacts (simple, no stock field)
# --------------------------------------------------------------------------------------
class FetchFromDBArtifact(BaseModel):
    limit: int
    start_date: str
    end_date: str
    only_missing_sentiment: bool = True


class IngestArtifact(BaseModel):
    published_at: List[str]
    title: List[str]
    description: List[str]
    url: List[str]
    source: List[str]


class SentimentArtifact(IngestArtifact):
    sentiment: List[str]
    sentiment_score: List[float]
    prob_pos: List[float]
    prob_neg: List[float]
    prob_neu: List[float]


# --------------------------------------------------------------------------------------
# Fetch / Score / Write
# --------------------------------------------------------------------------------------
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


def fetch_articles_from_db(engine, articles: Table, cols: set, artifact: FetchFromDBArtifact) -> IngestArtifact:
    """
    Fetch a batch of articles (newest first) that match filters.
    """
    where_clauses = []

    if artifact.only_missing_sentiment and "sentiment" in cols:
        where_clauses.append(articles.c.sentiment.is_(None))

    # Date window (timestamptz)
    start_dt = pd.to_datetime(artifact.start_date, utc=True, errors="raise")
    end_dt = pd.to_datetime(artifact.end_date, utc=True, errors="raise")

    where_clauses.append(articles.c.published_at >= start_dt.to_pydatetime())
    where_clauses.append(articles.c.published_at <= end_dt.to_pydatetime())

    # Select only columns that exist
    select_cols = [
        articles.c.published_at,
        articles.c.url,
    ]
    if "title" in cols:
        select_cols.append(articles.c.title)
    if "description" in cols:
        select_cols.append(articles.c.description)
    if "source" in cols:
        select_cols.append(articles.c.source)

    stmt = (
        select(*select_cols)
        .where(and_(*where_clauses))
        .order_by(articles.c.published_at.desc())
        .limit(int(artifact.limit))
    )

    logger.info(
        "[FetchFromDB] limit=%s start=%s end=%s only_missing=%s",
        artifact.limit,
        artifact.start_date,
        artifact.end_date,
        artifact.only_missing_sentiment,
    )

    with engine.connect() as conn:
        rows = conn.execute(stmt).fetchall()

    if not rows:
        return IngestArtifact(published_at=[], title=[], description=[], url=[], source=[])

    published_at_list: List[str] = []
    title_list: List[str] = []
    desc_list: List[str] = []
    url_list: List[str] = []
    source_list: List[str] = []

    # Row layout depends on which optional cols exist; unpack defensively
    for r in rows:
        # r always starts with published_at, url
        published_at = r[0]
        url = r[1]
        title = ""
        description = ""
        source = ""

        # remaining positions in the same order we appended
        idx = 2
        if "title" in cols:
            title = r[idx] if idx < len(r) else ""
            idx += 1
        if "description" in cols:
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
        title_list.append((title or "").strip())
        desc_list.append((description or "").strip())
        source_list.append((source or "").strip())

    return IngestArtifact(
        published_at=published_at_list,
        title=title_list,
        description=desc_list,
        url=url_list,
        source=source_list,
    )


def finbert_score(artifact: IngestArtifact) -> SentimentArtifact:
    if not artifact.url:
        return SentimentArtifact(
            published_at=[],
            title=[],
            description=[],
            url=[],
            source=[],
            sentiment=[],
            sentiment_score=[],
            prob_pos=[],
            prob_neg=[],
            prob_neu=[],
        )

    inputs = [_compose_text_for_finbert(t, d) for t, d in zip(artifact.title, artifact.description)]

    # If everything is empty, score neutral
    if not any(x.strip() for x in inputs):
        n = len(inputs)
        return SentimentArtifact(
            published_at=artifact.published_at,
            title=artifact.title,
            description=artifact.description,
            url=artifact.url,
            source=artifact.source,
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
        scores.append(pos - neg)  # your "sentiment_score"
        prob_pos.append(pos)
        prob_neg.append(neg)
        prob_neu.append(neu)

    return SentimentArtifact(
        published_at=artifact.published_at,
        title=artifact.title,
        description=artifact.description,
        url=artifact.url,
        source=artifact.source,
        sentiment=sentiments,
        sentiment_score=scores,
        prob_pos=prob_pos,
        prob_neg=prob_neg,
        prob_neu=prob_neu,
    )


def write_sentiment_to_db(engine, articles: Table, cols: set, artifact: SentimentArtifact) -> int:
    """
    Upsert by url. Only touches columns that exist.
    Returns # rows written (attempted).
    """
    n = len(artifact.url)
    if n == 0:
        return 0

    # Build records
    records: List[Dict[str, Any]] = []
    for i in range(n):
        url = artifact.url[i]
        if not url:
            continue

        dt = pd.to_datetime(artifact.published_at[i], utc=True, errors="coerce")
        if pd.isna(dt):
            continue

        rec: Dict[str, Any] = {"url": url}

        # Keep metadata consistent if those columns exist
        if "published_at" in cols:
            rec["published_at"] = dt.to_pydatetime()
        if "title" in cols:
            rec["title"] = (artifact.title[i] or None)
        if "description" in cols:
            rec["description"] = (artifact.description[i] or None)
        if "source" in cols:
            rec["source"] = (artifact.source[i] or None)

        # Sentiment fields (only if columns exist)
        if "sentiment" in cols:
            rec["sentiment"] = (artifact.sentiment[i] or None)
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

    # Build "set_" dict only for columns that exist (and that we provided)
    def _maybe_set(col_name: str, stmt) -> Optional[Tuple[str, Any]]:
        if col_name in cols:
            return (col_name, getattr(stmt.excluded, col_name))
        return None

    db_batch = int(os.getenv("FINBERT_DB_BATCH_SIZE", str(DEFAULT_DB_BATCH)))
    written = 0

    for i in range(0, len(records), db_batch):
        batch = records[i : i + db_batch]
        with engine.begin() as conn:
            stmt = insert(articles).values(batch)

            set_items = [
                _maybe_set("published_at", stmt),
                _maybe_set("title", stmt),
                _maybe_set("description", stmt),
                _maybe_set("source", stmt),
                _maybe_set("sentiment", stmt),
                _maybe_set("sentiment_score", stmt),
                _maybe_set("prob_pos", stmt),
                _maybe_set("prob_neg", stmt),
                _maybe_set("prob_neu", stmt),
            ]
            set_dict = {k: v for kv in set_items if kv is not None for (k, v) in [kv]}

            stmt = stmt.on_conflict_do_update(
                index_elements=["url"],
                set_=set_dict,
            )
            conn.execute(stmt)

        written += len(batch)
        logger.info(f"[WriteSentimentToDB] Processed {written}/{len(records)} in this batch-group")

    return len(records)


# --------------------------------------------------------------------------------------
# Main loop: process up to 5k missing-sentiment articles, in batches
# --------------------------------------------------------------------------------------
if __name__ == "__main__":
    db_url = build_db_url()
    engine = create_engine(db_url)
    articles, col_list = get_articles_table(engine)
    cols = set(col_list)

    # Inputs (no helper function; env still allowed but not required)
    start_date = os.getenv("FINBERT_START_DATE", "").strip() or DEFAULT_START_DATE
    end_date = os.getenv("FINBERT_END_DATE", "").strip() or DEFAULT_END_DATE

    # Total target in this run
    total_target = int(os.getenv("FINBERT_TOTAL", str(DEFAULT_TOTAL_TO_PROCESS)))

    # Fetch size per loop
    fetch_batch = int(os.getenv("FINBERT_FETCH_BATCH", str(DEFAULT_FETCH_BATCH)))

    only_missing = os.getenv("FINBERT_ONLY_MISSING", "true").strip().lower() in {"1", "true", "yes"}

    logger.info(
        "FinBERT run starting: window=%s..%s total_target=%s fetch_batch=%s only_missing=%s",
        start_date, end_date, total_target, fetch_batch, only_missing
    )

    total_fetched = 0
    total_written = 0
    loops = 0

    while total_fetched < total_target:
        loops += 1
        remaining = total_target - total_fetched
        this_limit = min(fetch_batch, remaining)

        fetch_art = FetchFromDBArtifact(
            limit=this_limit,
            start_date=start_date,
            end_date=end_date,
            only_missing_sentiment=only_missing,
        )

        batch = fetch_articles_from_db(engine, articles, cols, fetch_art)
        n = len(batch.url)

        if n == 0:
            logger.info("No more matching articles found. Stopping.")
            break

        logger.info(f"[Loop {loops}] fetched={n} (total_fetched would become {total_fetched + n}/{total_target})")

        scored = finbert_score(batch)
        written = write_sentiment_to_db(engine, articles, cols, scored)

        total_fetched += n
        total_written += written

        logger.info(f"[Loop {loops}] wrote={written} total_written={total_written}")

        # Safety: if we fetched less than requested, likely exhausted the query
        if n < this_limit:
            logger.info("Fetched fewer than requested in last batch; likely exhausted. Stopping.")
            break

    logger.info(
        "FinBERT run complete: total_fetched=%s total_written=%s window=%s..%s",
        total_fetched, total_written, start_date, end_date
    )