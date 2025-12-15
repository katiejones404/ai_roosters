from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Callable, Type

from datetime import datetime

import pandas as pd
import psycopg2
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline as hf_pipeline

logger = logging.getLogger("finbert_pipeline")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Device selection (prefer CUDA; fallback to CPU)
# ---------------------------------------------------------------------------

def select_device() -> int:
    """Return a Hugging Face `pipeline(..., device=...)` id.

    - `0` means CUDA GPU device 0
    - `-1` means CPU

    Prefers CUDA when available (e.g., NVIDIA Jetson Orin), but falls back to CPU
    if CUDA isn't available or can't be initialized.
    """

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

    # Some environments report cuda available but fail when actually creating tensors.
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
        # pydantic v1: dict(), v2: model_dump()
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

class DataArtifact(Artifact):
    # Input artifact for the ingest pipeline
    csv_path: str


class IngestArtifact(Artifact):
    published_at: List[str]
    title: List[str]
    description: List[str]
    url: List[str]


class SentimentArtifact(IngestArtifact):
    sentiment: List[str]
    sentiment_score: List[float]
    prob_pos: List[float]
    prob_neg: List[float]
    prob_neu: List[float]


class DBArtifact(Artifact):
    num_articles: int


# ---------------------------------------------------------------------------
# Stage 1: Load CSV → IngestArtifact
# ---------------------------------------------------------------------------

def load_csv_to_articles(artifact: DataArtifact) -> IngestArtifact:
    logger.info(f"[LoadCSV] Loading CSV from {artifact.csv_path}")
    df = pd.read_csv(artifact.csv_path)

    required_cols = ["published_at", "title", "description", "url"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"CSV must contain columns: {required_cols}")

    df["published_at"] = pd.to_datetime(df["published_at"])

    return IngestArtifact(
        published_at=df["published_at"].dt.strftime("%Y-%m-%dT%H:%M:%S %z").tolist(),
        title=df["title"].fillna("").tolist(),
        description=df["description"].fillna("").tolist(),
        url=df["url"].fillna("").tolist(),
    )


LoadStage = Stage(
    name="LoadCSV",
    input_schema=DataArtifact,
    output_schema=IngestArtifact,
    compute_fn=load_csv_to_articles,
)


# ---------------------------------------------------------------------------
# Stage 2: FinBERT sentiment analysis
# ---------------------------------------------------------------------------

_FINBERT_MODEL_ID = "ProsusAI/finbert"


def get_finbert_pipeline(*, force_cpu: bool = False):
    """
    Lazily load the FinBERT model. Keeps it in a function attribute so we only load once.
    """
    if not hasattr(get_finbert_pipeline, "finbert"):
        requested_device_id = -1 if force_cpu else select_device()

        def _build(device_id: int):
            logger.info(f"Loading FinBERT model (device_id={device_id})...")
            if device_id != -1:
                # On Jetson / constrained GPUs, fp16 greatly reduces memory pressure.
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


def finbert_articles(artifact: IngestArtifact) -> SentimentArtifact:
    logger.info("[FinBERTSentiment] Starting sentiment analysis...")

    if not artifact.description:
        logger.info("[FinBERTSentiment] No descriptions; returning empty sentiment lists.")
        return SentimentArtifact(
            published_at=artifact.published_at,
            title=artifact.title,
            description=artifact.description,
            url=artifact.url,
            sentiment=[],
            sentiment_score=[],
            prob_pos=[],
            prob_neg=[],
            prob_neu=[],
        )

    pipe = get_finbert_pipeline()

    # Default to conservative batching to avoid GPU OOM on Jetson.
    try:
        batch_size = int(os.getenv("FINBERT_BATCH_SIZE", "1"))
    except Exception:
        batch_size = 1

    try:
        results = pipe(artifact.description, batch_size=batch_size)
    except Exception as e:
        # If CUDA runtime fails (OOM, driver mismatch, etc.), retry once on CPU.
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
            results = pipe(artifact.description, batch_size=batch_size)
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
# Stage 3: Write to DB (articles table)
# ---------------------------------------------------------------------------

def write_articles_to_db(artifact: SentimentArtifact) -> DBArtifact:
    logger.info("[WriteArticlesToDB] Writing articles with sentiment into 'articles' table...")

    dsn = os.getenv(
        "DATABASE_URL",
        "postgresql://stock_user:stock_pass@postgres:5432/stock_db",
    )
    conn = psycopg2.connect(dsn)

    num_articles = 0
    rows = zip(
        artifact.published_at,
        artifact.title,
        artifact.description,
        artifact.url,
        artifact.sentiment,
        artifact.sentiment_score,
        artifact.prob_pos,
        artifact.prob_neg,
        artifact.prob_neu,
    )

    with conn.cursor() as cur:
        for (
            published_at,
            title,
            description,
            url,
            sentiment,
            sentiment_score,
            prob_pos,
            prob_neg,
            prob_neu,
        ) in rows:
            num_articles += 1
            cur.execute(
                """
                INSERT INTO articles (
                    published_at,
                    title,
                    description,
                    url,
                    sentiment,
                    sentiment_score,
                    prob_pos,
                    prob_neg,
                    prob_neu
                )
                VALUES (
                    %(published_at)s,
                    %(title)s,
                    %(description)s,
                    %(url)s,
                    %(sentiment)s,
                    %(sentiment_score)s,
                    %(prob_pos)s,
                    %(prob_neg)s,
                    %(prob_neu)s
                )
                ON CONFLICT (url) DO UPDATE SET
                    published_at    = EXCLUDED.published_at,
                    title           = EXCLUDED.title,
                    description     = EXCLUDED.description,
                    sentiment       = EXCLUDED.sentiment,
                    sentiment_score = EXCLUDED.sentiment_score,
                    prob_pos        = EXCLUDED.prob_pos,
                    prob_neg        = EXCLUDED.prob_neg,
                    prob_neu        = EXCLUDED.prob_neu;
                """,
                {
                    "published_at": published_at,
                    "title": title,
                    "description": description,
                    "url": url,
                    "sentiment": sentiment,
                    "sentiment_score": sentiment_score,
                    "prob_pos": prob_pos,
                    "prob_neg": prob_neg,
                    "prob_neu": prob_neu,
                },
            )

    conn.commit()
    conn.close()

    logger.info(f"[WriteArticlesToDB] Finished. num_articles={num_articles}")
    return DBArtifact(num_articles=num_articles)


DBStage = Stage(
    name="WriteArticlesToDB",
    input_schema=SentimentArtifact,
    output_schema=DBArtifact,
    compute_fn=write_articles_to_db,
)


# ---------------------------------------------------------------------------
# Pipeline definition + helper for FastAPI startup
# ---------------------------------------------------------------------------

finbert_ingest_pipeline = Pipeline(
    "FinbertCSVtoArticlesDB",
    [LoadStage, FinBERTStage, DBStage],
)


def run_finbert_pipeline_from_env() -> Dict[str, Any]:
    """
    Run the FinBERT ingest pipeline using NEWS_CSV_PATH env var.
    This is what you'll call from FastAPI startup.
    """
    csv_path = os.getenv("NEWS_CSV_PATH", "/app/data/reliance_news_sentiment.csv")
    logger.info(f"Running FinBERT ingest pipeline with csv_path={csv_path!r} ...")

    result = finbert_ingest_pipeline.run({"csv_path": csv_path})
    logger.info(f"FinBERT pipeline result: {result}")
    return result


if __name__ == "__main__":
    # CLI usage (optional)
    run_finbert_pipeline_from_env()
