from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Callable, Type, Optional, Tuple

import pandas as pd
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline as hf_pipeline

from sqlalchemy import create_engine, MetaData, Table, select, and_, or_
from sqlalchemy.dialects.postgresql import insert


logger = logging.getLogger("finbert_pipeline")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

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


def get_articles_table(engine) -> Table:
    metadata = MetaData()
    metadata.reflect(engine, only=["articles"])
    if "articles" not in metadata.tables:
        raise RuntimeError("Table 'articles' does not exist in the database.")
    return metadata.tables["articles"]


# ---------------------------------------------------------------------------
# Device selection (prefer CUDA; fallback to CPU)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Core “Artifact” + Pipeline abstractions
# ---------------------------------------------------------------------------

class Artifact(BaseModel):
    def to_json(self) -> Dict[str, Any]:
        if hasattr(self, "model_dump"):
            return self.model_dump()
        return self.dict()


class Stage:
    def __init__(
        self,
        name: str,
        input_schema: Type[Artifact],
        output_schema: Type[Artifact],
        compute_fn: Callable[[Artifact], Artifact],
    ):
        self.name = name
        self.input_schema = input_schema
        self.output_schema = output_schema
        self.compute_fn = compute_fn

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"[{self.name}] Validating input...")
        artifact_in = self.input_schema(**input_data)

        logger.info(f"[{self.name}] Computing...")
        artifact_out = self.compute_fn(artifact_in)

        logger.info(f"[{self.name}] Validating output...")
        artifact_valid = self.output_schema(**artifact_out.to_json())

        logger.info(f"[{self.name}] Completed successfully.")
        return artifact_valid.to_json()


class Pipeline:
    def __init__(self, name: str, stages: List[Stage]):
        self.name = name
        self.stages = stages

    def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Pipeline '{self.name}' starting...")
        for s in self.stages:
            data = s.run(data)
        logger.info(f"Pipeline '{self.name}' completed.")
        return data


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------

class FetchFromDBArtifact(Artifact):
    limit: int = 1000
    stocks_csv: str = ""           # optional: "AAPL,MSFT"
    start_date: str = ""           # optional ISO like "2018-01-01"
    end_date: str = ""             # optional ISO like "2024-12-01"
    only_missing_sentiment: bool = True


class IngestArtifact(Artifact):
    published_at: List[str]
    title: List[str]
    description: List[str]
    url: List[str]
    stock: List[str]
    source: List[str]


class SentimentArtifact(IngestArtifact):
    sentiment: List[str]
    sentiment_score: List[float]
    prob_pos: List[float]
    prob_neg: List[float]
    prob_neu: List[float]


class DBArtifact(Artifact):
    num_articles_fetched: int
    num_articles_scored: int
    num_rows_written: int


# ---------------------------------------------------------------------------
# Stage 1: Fetch from DB → IngestArtifact
# ---------------------------------------------------------------------------

def _parse_stocks_csv(stocks_csv: str) -> List[str]:
    if not stocks_csv:
        return []
    parts = [p.strip().upper() for p in stocks_csv.split(",")]
    return [p for p in parts if p]


def fetch_articles_from_db(artifact: FetchFromDBArtifact) -> IngestArtifact:
    db_url = build_db_url()
    engine = create_engine(db_url)
    articles = get_articles_table(engine)

    stocks = _parse_stocks_csv(artifact.stocks_csv)

    where_clauses = []

    if artifact.only_missing_sentiment:
        # treat "missing" as NULL sentiment (you can expand to score/prob columns too)
        where_clauses.append(articles.c.sentiment.is_(None))

    if stocks:
        where_clauses.append(articles.c.stock.in_(stocks))

    # Optional date filters
    # published_at is timestamptz; we compare using parsed timestamps (UTC)
    if artifact.start_date:
        start_dt = pd.to_datetime(artifact.start_date, utc=True, errors="raise")
        where_clauses.append(articles.c.published_at >= start_dt.to_pydatetime())

    if artifact.end_date:
        end_dt = pd.to_datetime(artifact.end_date, utc=True, errors="raise")
        where_clauses.append(articles.c.published_at <= end_dt.to_pydatetime())

    # Build query
    stmt = (
        select(
            articles.c.published_at,
            articles.c.title,
            articles.c.description,
            articles.c.url,
            articles.c.stock,
            articles.c.source,
        )
        .where(and_(*where_clauses) if where_clauses else True)
        .order_by(articles.c.published_at.desc())
        .limit(int(artifact.limit))
    )

    logger.info(
        "[FetchFromDB] Querying articles (limit=%s, stocks=%s, start=%s, end=%s, missing_sentiment=%s)",
        artifact.limit,
        stocks or "ALL",
        artifact.start_date or "NONE",
        artifact.end_date or "NONE",
        artifact.only_missing_sentiment,
    )

    rows: List[Tuple] = []
    with engine.connect() as conn:
        rows = conn.execute(stmt).fetchall()

    if not rows:
        logger.info("[FetchFromDB] No matching rows found.")
        return IngestArtifact(
            published_at=[],
            title=[],
            description=[],
            url=[],
            stock=[],
            source=[],
        )

    # Normalize + ensure strings
    published_at_list: List[str] = []
    title_list: List[str] = []
    desc_list: List[str] = []
    url_list: List[str] = []
    stock_list: List[str] = []
    source_list: List[str] = []

    for published_at, title, description, url, stock, source in rows:
        if not url:
            continue

        # published_at to RFC-ish Z string
        dt = pd.to_datetime(published_at, utc=True, errors="coerce")
        if pd.isna(dt):
            continue

        published_at_list.append(dt.strftime("%Y-%m-%dT%H:%M:%SZ"))
        title_list.append((title or "").strip())
        desc_list.append((description or "").strip())
        url_list.append(str(url).strip())
        stock_list.append((stock or "").strip().upper())
        source_list.append((source or "").strip())

    logger.info("[FetchFromDB] Fetched %d rows from DB.", len(url_list))
    return IngestArtifact(
        published_at=published_at_list,
        title=title_list,
        description=desc_list,
        url=url_list,
        stock=stock_list,
        source=source_list,
    )


FetchStage = Stage(
    name="FetchFromDB",
    input_schema=FetchFromDBArtifact,
    output_schema=IngestArtifact,
    compute_fn=fetch_articles_from_db,
)


# ---------------------------------------------------------------------------
# Stage 2: FinBERT sentiment analysis
# ---------------------------------------------------------------------------

_FINBERT_MODEL_ID = "ProsusAI/finbert"


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


def scores_dict(all_scores: List[Dict[str, float]]) -> Dict[str, float]:
    d = {e["label"].lower(): float(e["score"]) for e in all_scores}
    for k in ("positive", "neutral", "negative"):
        d.setdefault(k, 0.0)
    return d


def _compose_text_for_finbert(title: str, description: str) -> str:
    title = (title or "").strip()
    description = (description or "").strip()
    if title and description:
        return f"{title}. {description}"
    return title or description


def finbert_articles(artifact: IngestArtifact) -> SentimentArtifact:
    logger.info("[FinBERTSentiment] Starting sentiment analysis...")

    if not artifact.url:
        logger.info("[FinBERTSentiment] No articles provided; returning empty.")
        return SentimentArtifact(
            published_at=[],
            title=[],
            description=[],
            url=[],
            stock=[],
            source=[],
            sentiment=[],
            sentiment_score=[],
            prob_pos=[],
            prob_neg=[],
            prob_neu=[],
        )

    inputs = [
        _compose_text_for_finbert(t, d)
        for t, d in zip(artifact.title, artifact.description)
    ]

    # Skip completely empty inputs but keep alignment by url
    # We'll score empty ones as neutral/0.0 by default.
    has_any = any(x.strip() for x in inputs)
    if not has_any:
        logger.info("[FinBERTSentiment] All inputs empty; scoring as neutral/0.0.")
        n = len(inputs)
        return SentimentArtifact(
            published_at=artifact.published_at,
            title=artifact.title,
            description=artifact.description,
            url=artifact.url,
            stock=artifact.stock,
            source=artifact.source,
            sentiment=["neutral"] * n,
            sentiment_score=[0.0] * n,
            prob_pos=[0.0] * n,
            prob_neg=[0.0] * n,
            prob_neu=[1.0] * n,
        )

    pipe = get_finbert_pipeline()

    try:
        batch_size = int(os.getenv("FINBERT_BATCH_SIZE", "8"))
    except Exception:
        batch_size = 8

    try:
        results = pipe(inputs, batch_size=batch_size)
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
            results = pipe(inputs, batch_size=batch_size)
        else:
            raise

    sentiments: List[str] = []
    scores: List[float] = []
    prob_pos: List[float] = []
    prob_neg: List[float] = []
    prob_neu: List[float] = []

    for result in results:
        score_map = scores_dict(result)
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
        published_at=artifact.published_at,
        title=artifact.title,
        description=artifact.description,
        url=artifact.url,
        stock=artifact.stock,
        source=artifact.source,
        sentiment=sentiments,
        sentiment_score=scores,
        prob_pos=prob_pos,
        prob_neg=prob_neg,
        prob_neu=prob_neu,
    )


FinBERTStage = Stage(
    name="FinBERTSentiment",
    input_schema=IngestArtifact,
    output_schema=SentimentArtifact,
    compute_fn=finbert_articles,
)


# ---------------------------------------------------------------------------
# Stage 3: Write sentiment back to DB (upsert by url)
# ---------------------------------------------------------------------------

def write_sentiment_to_db(artifact: SentimentArtifact) -> DBArtifact:
    db_url = build_db_url()
    engine = create_engine(db_url)
    articles = get_articles_table(engine)

    n_fetched = len(artifact.url)
    if n_fetched == 0:
        return DBArtifact(num_articles_fetched=0, num_articles_scored=0, num_rows_written=0)

    # If sentiment arrays are empty for some reason, we won't write.
    if not artifact.sentiment or len(artifact.sentiment) != n_fetched:
        raise RuntimeError("Sentiment output length mismatch with fetched articles.")

    rows = zip(
        artifact.published_at,
        artifact.title,
        artifact.description,
        artifact.url,
        artifact.stock,
        artifact.source,
        artifact.sentiment,
        artifact.sentiment_score,
        artifact.prob_pos,
        artifact.prob_neg,
        artifact.prob_neu,
    )

    records: List[Dict[str, Any]] = []
    for (
        published_at,
        title,
        description,
        url,
        stock,
        source,
        sentiment,
        sentiment_score,
        prob_pos,
        prob_neg,
        prob_neu,
    ) in rows:
        if not url:
            continue

        dt = pd.to_datetime(published_at, utc=True, errors="coerce")
        if pd.isna(dt):
            continue

        records.append(
            {
                "url": url,
                # keep metadata consistent
                "published_at": dt.to_pydatetime(),
                "title": title or None,
                "description": description or None,
                "source": source or None,
                "stock": stock or None,
                # sentiment fields
                "sentiment": sentiment or None,
                "sentiment_score": float(sentiment_score) if sentiment_score is not None else None,
                "prob_pos": float(prob_pos) if prob_pos is not None else None,
                "prob_neg": float(prob_neg) if prob_neg is not None else None,
                "prob_neu": float(prob_neu) if prob_neu is not None else None,
            }
        )

    if not records:
        return DBArtifact(num_articles_fetched=n_fetched, num_articles_scored=0, num_rows_written=0)

    batch_size = int(os.getenv("FINBERT_DB_BATCH_SIZE", "250"))
    written = 0

    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        with engine.begin() as conn:
            stmt = insert(articles).values(batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=["url"],
                set_={
                    "published_at": stmt.excluded.published_at,
                    "title": stmt.excluded.title,
                    "description": stmt.excluded.description,
                    "source": stmt.excluded.source,
                    "stock": stmt.excluded.stock,
                    "sentiment": stmt.excluded.sentiment,
                    "sentiment_score": stmt.excluded.sentiment_score,
                    "prob_pos": stmt.excluded.prob_pos,
                    "prob_neg": stmt.excluded.prob_neg,
                    "prob_neu": stmt.excluded.prob_neu,
                },
            )
            conn.execute(stmt)

        written += len(batch)
        logger.info(f"[WriteSentimentToDB] Processed {written}/{len(records)}")

    return DBArtifact(
        num_articles_fetched=n_fetched,
        num_articles_scored=n_fetched,
        num_rows_written=len(records),
    )


DBStage = Stage(
    name="WriteSentimentToDB",
    input_schema=SentimentArtifact,
    output_schema=DBArtifact,
    compute_fn=write_sentiment_to_db,
)


# ---------------------------------------------------------------------------
# Pipeline definition + helper runner
# ---------------------------------------------------------------------------

finbert_db_pipeline = Pipeline(
    "FinbertDBtoArticlesDB",
    [FetchStage, FinBERTStage, DBStage],
)


def run_finbert_pipeline_from_env() -> Dict[str, Any]:
    """
    Run FinBERT over articles in Postgres that are missing sentiment.
    Environment variables:
      FINBERT_FETCH_LIMIT (default 1000)
      FINBERT_STOCKS (optional "AAPL,MSFT")
      FINBERT_START_DATE (optional "2018-01-01")
      FINBERT_END_DATE (optional "2024-12-01")
      FINBERT_ONLY_MISSING (default true)
      FINBERT_BATCH_SIZE (default 8)
      FINBERT_DB_BATCH_SIZE (default 250)
    """
    limit = int(os.getenv("FINBERT_FETCH_LIMIT", "1000"))
    stocks = os.getenv("FINBERT_STOCKS", "")
    start_date = os.getenv("FINBERT_START_DATE", "")
    end_date = os.getenv("FINBERT_END_DATE", "")
    only_missing = os.getenv("FINBERT_ONLY_MISSING", "true").strip().lower() in {"1", "true", "yes"}

    logger.info(
        "Running FinBERT DB pipeline with limit=%s stocks=%r start=%r end=%r only_missing=%s",
        limit, stocks, start_date, end_date, only_missing
    )

    result = finbert_db_pipeline.run(
        {
            "limit": limit,
            "stocks_csv": stocks,
            "start_date": start_date,
            "end_date": end_date,
            "only_missing_sentiment": only_missing,
        }
    )
    logger.info(f"FinBERT DB pipeline result: {result}")
    return result


if __name__ == "__main__":
    run_finbert_pipeline_from_env()