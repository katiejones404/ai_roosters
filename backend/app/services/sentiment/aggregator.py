"""
Sentiment aggregation and XGBoost return prediction pipeline for StockSense.

Joins daily stock price rows with FinBERT-scored article sentiment from both
the broad articles table and ticker-specific stock_news_articles, trains XGBoost
regression models for each return horizon, then writes the combined snapshot rows
to sentiment_snapshots. Runs as a four-stage pipeline: load stocks, aggregate
sentiment, XGBoost predictions, write to DB.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Callable, Type, Optional
from datetime import date, datetime
import math

import psycopg2
import numpy as np
from xgboost import XGBRegressor

# Basic logger setup for the pipeline
logger = logging.getLogger("snapshot_pipeline")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(_handler)

# Keep this list aligned with the app's tracked tickers
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
# Oldest date this pipeline will allow
PIPELINE_MIN_DATE = date(2020, 1, 1)

try:
    from pydantic import BaseModel
except ImportError:
    class BaseModel:
        model_fields: Dict[str, Any] = {}

        def __init__(self, **data: Any):
            for k, v in data.items():
                setattr(self, k, v)

        def model_dump(self) -> Dict[str, Any]:
            return self.__dict__.copy()


# Small base artifact with a helper for JSON-like output
class Artifact(BaseModel):
    def to_json(self) -> Dict[str, Any]:
        if hasattr(self, "model_dump"):
            return self.model_dump()
        if hasattr(self, "dict"):
            return self.dict()
        return self.__dict__.copy()


# Simple pipeline stage wrapper with input and output validation
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


# Runs each stage in order and passes data along
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


# Input request for the snapshot pipeline
class SnapshotRequestArtifact(Artifact):
    ticker: Optional[str] = None
    tickers: Optional[List[str]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


# Raw stock rows loaded from the database
class StockRowsArtifact(Artifact):
    ticker: List[str]
    date: List[str]
    close_price: List[Optional[float]]
    return_1d: List[Optional[float]]
    return_30d: List[Optional[float]]
    return_120d: List[Optional[float]]
    return_360d: List[Optional[float]]


# Combined stock and sentiment snapshot data
class SentimentAggregateArtifact(Artifact):
    ticker: List[str]
    snapshot_date: List[str]
    close_price: List[Optional[float]]
    return_1d: List[Optional[float]]
    return_30d: List[Optional[float]]
    return_120d: List[Optional[float]]
    return_360d: List[Optional[float]]

    sentiment_mean: List[Optional[float]]
    sentiment_max: List[Optional[float]]
    sentiment_min: List[Optional[float]]

    num_articles: List[int]
    num_pos_articles: List[int]
    num_neg_articles: List[int]

    pos_share: List[Optional[float]]
    neg_share: List[Optional[float]]

    prob_pos_mean: List[Optional[float]]
    prob_neg_mean: List[Optional[float]]
    prob_neu_mean: List[Optional[float]]

    prob_pos_max: List[Optional[float]]
    prob_neg_max: List[Optional[float]]

    pred_return_1d: Optional[List[Optional[float]]] = None
    pred_return_30d: Optional[List[Optional[float]]] = None
    pred_return_120d: Optional[List[Optional[float]]] = None
    pred_return_360d: Optional[List[Optional[float]]] = None


# Final DB write result
class DBArtifact(Artifact):
    num_snapshots: int


# Builds the database connection string
def _get_dsn() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql://stock_user:stock_pass@postgres:5432/stock_db",
    )


# Quick ISO date parser
def _parse_date(s: str) -> date:
    return datetime.fromisoformat(s).date()


# Reads common true or false style env values
def _truthy_env(name: str, default: str = "0") -> bool:
    val = os.getenv(name, default).strip().lower()
    return val in {"1", "true", "t", "yes", "y", "on"}


# Checks if xgboost supports CUDA on this setup
def _xgb_has_cuda_build() -> bool:
    try:
        import xgboost as xgb
        bi = getattr(xgb, "build_info", None)
        if not callable(bi):
            return False
        info = bi()
        if not isinstance(info, dict):
            return False
        use_cuda = info.get("USE_CUDA", info.get("use_cuda"))
        if isinstance(use_cuda, bool):
            return use_cuda
        if isinstance(use_cuda, str):
            return use_cuda.strip().lower() in {"1", "true", "yes", "y", "on"}
        return False
    except Exception:
        return False


# Keeps model features finite and safe
def _safe_num(x: Optional[float]) -> float:
    if x is None:
        return 0.0
    v = float(x)
    if not math.isfinite(v):
        return 0.0
    return v


# Makes sure the start date is valid and not too early
def _normalize_pipeline_start_date(raw_start: Optional[str]) -> str:
    candidate = (raw_start or "").strip() or PIPELINE_MIN_DATE.isoformat()
    try:
        parsed = datetime.fromisoformat(candidate).date()
    except ValueError:
        logger.warning("Invalid AGG_START_DATE/start_date=%r, using %s", candidate, PIPELINE_MIN_DATE.isoformat())
        return PIPELINE_MIN_DATE.isoformat()
    if parsed < PIPELINE_MIN_DATE:
        return PIPELINE_MIN_DATE.isoformat()
    return parsed.isoformat()


# Chooses tickers from the request, env, or defaults
def _pick_tickers(req: SnapshotRequestArtifact) -> List[str]:
    if req.ticker:
        return [req.ticker]
    if req.tickers:
        return [t for t in req.tickers if t]
    env = (os.getenv("AGG_TICKERS") or "").strip()
    if env:
        return [t.strip().upper() for t in env.split(",") if t.strip()]
    return TARGET_TICKERS.copy()


# Loads stock rows and return columns from the DB
def load_stock_rows(req: SnapshotRequestArtifact) -> StockRowsArtifact:
    logger.info("[LoadStocks] Fetching stock rows from database")

    dsn = _get_dsn()
    conn = psycopg2.connect(dsn)
    cur = conn.cursor()

    tickers = _pick_tickers(req)
    start_date = _normalize_pipeline_start_date(req.start_date or os.getenv("AGG_START_DATE"))
    end_date = req.end_date or os.getenv("AGG_END_DATE") or date.today().isoformat()

    sql = """
        SELECT
            ticker,
            date,
            close,
            return_1d,
            return_30d,
            return_120d,
            return_360d
        FROM stocks
        WHERE ticker = ANY(%s)
          AND date >= %s
          AND date <= %s
        ORDER BY ticker, date
    """

    cur.execute(sql, (tickers, start_date, end_date))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    out_ticker: List[str] = []
    dates: List[str] = []
    close_price: List[Optional[float]] = []
    r1d: List[Optional[float]] = []
    r30d: List[Optional[float]] = []
    r120d: List[Optional[float]] = []
    r360d: List[Optional[float]] = []

    for (t, d, close, ret1, ret30, ret120, ret360) in rows:
        out_ticker.append(str(t))
        dates.append(d.isoformat() if isinstance(d, date) else str(d))
        close_price.append(float(close) if close is not None else None)
        r1d.append(float(ret1) if ret1 is not None else None)
        r30d.append(float(ret30) if ret30 is not None else None)
        r120d.append(float(ret120) if ret120 is not None else None)
        r360d.append(float(ret360) if ret360 is not None else None)

    logger.info(f"[LoadStocks] Loaded {len(out_ticker)} stock rows across {len(set(out_ticker)) if out_ticker else 0} tickers")

    return StockRowsArtifact(
        ticker=out_ticker,
        date=dates,
        close_price=close_price,
        return_1d=r1d,
        return_30d=r30d,
        return_120d=r120d,
        return_360d=r360d,
    )


# Stage 1: load stock price rows
LoadStocksStage = Stage(
    name="LoadStocks",
    input_schema=SnapshotRequestArtifact,
    output_schema=StockRowsArtifact,
    compute_fn=load_stock_rows,
)


# Daily aggregates from the broad articles table
def _fetch_broad_daily(cur, min_date_val: date, max_date_val: date) -> Dict[date, Dict[str, Any]]:
    cur.execute(
        """
        SELECT
            published_at::date AS pub_date,
            COUNT(*) FILTER (WHERE sentiment IS NOT NULL) AS n_labeled,
            COUNT(*) FILTER (WHERE sentiment = 'positive') AS n_pos,
            COUNT(*) FILTER (WHERE sentiment = 'negative') AS n_neg,

            AVG(sentiment_score) FILTER (WHERE sentiment_score IS NOT NULL) AS mean_score,
            MAX(sentiment_score) FILTER (WHERE sentiment_score IS NOT NULL) AS max_score,
            MIN(sentiment_score) FILTER (WHERE sentiment_score IS NOT NULL) AS min_score,

            AVG(prob_pos) FILTER (WHERE prob_pos IS NOT NULL) AS prob_pos_mean,
            AVG(prob_neg) FILTER (WHERE prob_neg IS NOT NULL) AS prob_neg_mean,
            AVG(prob_neu) FILTER (WHERE prob_neu IS NOT NULL) AS prob_neu_mean,

            MAX(prob_pos) FILTER (WHERE prob_pos IS NOT NULL) AS prob_pos_max,
            MAX(prob_neg) FILTER (WHERE prob_neg IS NOT NULL) AS prob_neg_max
        FROM articles
        WHERE published_at IS NOT NULL
          AND published_at::date BETWEEN %s AND %s
        GROUP BY 1
        ORDER BY 1;
        """,
        (min_date_val, max_date_val),
    )

    out: Dict[date, Dict[str, Any]] = {}
    for row in cur.fetchall():
        pub_date, n_labeled, n_pos, n_neg, mean_score, max_score, min_score, pp_mean, pn_mean, pneu_mean, pp_max, pn_max = row
        d = pub_date if isinstance(pub_date, date) else _parse_date(str(pub_date))
        nl = int(n_labeled or 0)
        np_ = int(n_pos or 0)
        nn_ = int(n_neg or 0)
        out[d] = {
            "num_articles": nl,
            "num_pos_articles": np_,
            "num_neg_articles": nn_,
            "sentiment_mean": float(mean_score) if mean_score is not None else None,
            "sentiment_max": float(max_score) if max_score is not None else None,
            "sentiment_min": float(min_score) if min_score is not None else None,
            "prob_pos_mean": float(pp_mean) if pp_mean is not None else None,
            "prob_neg_mean": float(pn_mean) if pn_mean is not None else None,
            "prob_neu_mean": float(pneu_mean) if pneu_mean is not None else None,
            "prob_pos_max": float(pp_max) if pp_max is not None else None,
            "prob_neg_max": float(pn_max) if pn_max is not None else None,
        }
    return out


# Daily aggregates from ticker-specific stock news
def _fetch_stock_news_daily(cur, min_date_val: date, max_date_val: date, tickers: List[str]) -> Dict[tuple, Dict[str, Any]]:
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'stock_news_articles'
              AND column_name = 'sentiment'
        );
        """
    )
    has_sentiment = bool(cur.fetchone()[0])
    if not has_sentiment:
        logger.warning("[AggregateSentiment] stock_news_articles has no sentiment columns yet; skipping stock-news contribution")
        return {}

    cur.execute(
        """
        SELECT
            ticker,
            published_at::date AS pub_date,
            COUNT(*) FILTER (WHERE sentiment IS NOT NULL) AS n_labeled,
            COUNT(*) FILTER (WHERE sentiment = 'positive') AS n_pos,
            COUNT(*) FILTER (WHERE sentiment = 'negative') AS n_neg,

            AVG(sentiment_score) FILTER (WHERE sentiment_score IS NOT NULL) AS mean_score,
            MAX(sentiment_score) FILTER (WHERE sentiment_score IS NOT NULL) AS max_score,
            MIN(sentiment_score) FILTER (WHERE sentiment_score IS NOT NULL) AS min_score,

            AVG(prob_pos) FILTER (WHERE prob_pos IS NOT NULL) AS prob_pos_mean,
            AVG(prob_neg) FILTER (WHERE prob_neg IS NOT NULL) AS prob_neg_mean,
            AVG(prob_neu) FILTER (WHERE prob_neu IS NOT NULL) AS prob_neu_mean,

            MAX(prob_pos) FILTER (WHERE prob_pos IS NOT NULL) AS prob_pos_max,
            MAX(prob_neg) FILTER (WHERE prob_neg IS NOT NULL) AS prob_neg_max
        FROM stock_news_articles
        WHERE published_at IS NOT NULL
          AND ticker = ANY(%s)
          AND published_at::date BETWEEN %s AND %s
        GROUP BY 1, 2
        ORDER BY 1, 2;
        """,
        (tickers, min_date_val, max_date_val),
    )

    out: Dict[tuple, Dict[str, Any]] = {}
    for row in cur.fetchall():
        tkr, pub_date, n_labeled, n_pos, n_neg, mean_score, max_score, min_score, pp_mean, pn_mean, pneu_mean, pp_max, pn_max = row
        d = pub_date if isinstance(pub_date, date) else _parse_date(str(pub_date))
        nl = int(n_labeled or 0)
        np_ = int(n_pos or 0)
        nn_ = int(n_neg or 0)
        out[(str(tkr), d)] = {
            "num_articles": nl,
            "num_pos_articles": np_,
            "num_neg_articles": nn_,
            "sentiment_mean": float(mean_score) if mean_score is not None else None,
            "sentiment_max": float(max_score) if max_score is not None else None,
            "sentiment_min": float(min_score) if min_score is not None else None,
            "prob_pos_mean": float(pp_mean) if pp_mean is not None else None,
            "prob_neg_mean": float(pn_mean) if pn_mean is not None else None,
            "prob_neu_mean": float(pneu_mean) if pneu_mean is not None else None,
            "prob_pos_max": float(pp_max) if pp_max is not None else None,
            "prob_neg_max": float(pn_max) if pn_max is not None else None,
        }
    return out


# Blends two averages using article counts
def _weighted_mean(a: Optional[float], an: int, b: Optional[float], bn: int) -> Optional[float]:
    an_eff = an if a is not None else 0
    bn_eff = bn if b is not None else 0
    denom = an_eff + bn_eff
    if denom == 0:
        return None
    total = (float(a) * an_eff if a is not None else 0.0) + (float(b) * bn_eff if b is not None else 0.0)
    return total / denom


# Keeps the larger non-null value
def _combine_max(a: Optional[float], b: Optional[float]) -> Optional[float]:
    vals = [v for v in (a, b) if v is not None]
    return max(vals) if vals else None


# Keeps the smaller non-null value
def _combine_min(a: Optional[float], b: Optional[float]) -> Optional[float]:
    vals = [v for v in (a, b) if v is not None]
    return min(vals) if vals else None


# Merges stock rows with daily sentiment data
def aggregate_sentiment(stocks: StockRowsArtifact) -> SentimentAggregateArtifact:
    logger.info("[AggregateSentiment] Aggregating broad articles + ticker-specific stock_news_articles")

    n = len(stocks.ticker)
    if n == 0:
        return SentimentAggregateArtifact(
            ticker=[],
            snapshot_date=[],
            close_price=[],
            return_1d=[],
            return_30d=[],
            return_120d=[],
            return_360d=[],
            sentiment_mean=[],
            sentiment_max=[],
            sentiment_min=[],
            num_articles=[],
            num_pos_articles=[],
            num_neg_articles=[],
            pos_share=[],
            neg_share=[],
            prob_pos_mean=[],
            prob_neg_mean=[],
            prob_neu_mean=[],
            prob_pos_max=[],
            prob_neg_max=[],
        )

    all_dates = [_parse_date(d) for d in stocks.date]
    min_date_val = min(all_dates)
    max_date_val = max(all_dates)
    unique_tickers = sorted(set(stocks.ticker))

    dsn = _get_dsn()
    conn = psycopg2.connect(dsn)
    cur = conn.cursor()

    broad_daily = _fetch_broad_daily(cur, min_date_val, max_date_val)
    stock_news_daily = _fetch_stock_news_daily(cur, min_date_val, max_date_val, unique_tickers)

    cur.close()
    conn.close()

    out_ticker: List[str] = []
    out_date: List[str] = []
    out_close: List[Optional[float]] = []
    out_r1d: List[Optional[float]] = []
    out_r30d: List[Optional[float]] = []
    out_r120d: List[Optional[float]] = []
    out_r360d: List[Optional[float]] = []

    sent_mean: List[Optional[float]] = []
    sent_max: List[Optional[float]] = []
    sent_min: List[Optional[float]] = []

    num_articles: List[int] = []
    num_pos: List[int] = []
    num_neg: List[int] = []
    pos_share: List[Optional[float]] = []
    neg_share: List[Optional[float]] = []

    prob_pos_mean: List[Optional[float]] = []
    prob_neg_mean: List[Optional[float]] = []
    prob_neu_mean: List[Optional[float]] = []
    prob_pos_max: List[Optional[float]] = []
    prob_neg_max: List[Optional[float]] = []

    for i in range(n):
        t = stocks.ticker[i]
        d = _parse_date(stocks.date[i])

        broad = broad_daily.get(d, {})
        specific = stock_news_daily.get((t, d), {})

        broad_n = int(broad.get("num_articles", 0))
        stock_n = int(specific.get("num_articles", 0))
        total_n = broad_n + stock_n

        broad_pos = int(broad.get("num_pos_articles", 0))
        stock_pos = int(specific.get("num_pos_articles", 0))
        total_pos = broad_pos + stock_pos

        broad_neg = int(broad.get("num_neg_articles", 0))
        stock_neg = int(specific.get("num_neg_articles", 0))
        total_neg = broad_neg + stock_neg

        sent_mean.append(_weighted_mean(broad.get("sentiment_mean"), broad_n, specific.get("sentiment_mean"), stock_n))
        sent_max.append(_combine_max(broad.get("sentiment_max"), specific.get("sentiment_max")))
        sent_min.append(_combine_min(broad.get("sentiment_min"), specific.get("sentiment_min")))

        num_articles.append(total_n)
        num_pos.append(total_pos)
        num_neg.append(total_neg)

        pos_share.append((float(total_pos) / total_n) if total_n > 0 else None)
        neg_share.append((float(total_neg) / total_n) if total_n > 0 else None)

        prob_pos_mean.append(_weighted_mean(broad.get("prob_pos_mean"), broad_n, specific.get("prob_pos_mean"), stock_n))
        prob_neg_mean.append(_weighted_mean(broad.get("prob_neg_mean"), broad_n, specific.get("prob_neg_mean"), stock_n))
        prob_neu_mean.append(_weighted_mean(broad.get("prob_neu_mean"), broad_n, specific.get("prob_neu_mean"), stock_n))
        prob_pos_max.append(_combine_max(broad.get("prob_pos_max"), specific.get("prob_pos_max")))
        prob_neg_max.append(_combine_max(broad.get("prob_neg_max"), specific.get("prob_neg_max")))

        out_ticker.append(t)
        out_date.append(d.isoformat())
        out_close.append(stocks.close_price[i])
        out_r1d.append(stocks.return_1d[i])
        out_r30d.append(stocks.return_30d[i])
        out_r120d.append(stocks.return_120d[i])
        out_r360d.append(stocks.return_360d[i])

    logger.info("[AggregateSentiment] Built %s combined snapshot rows", len(out_ticker))

    return SentimentAggregateArtifact(
        ticker=out_ticker,
        snapshot_date=out_date,
        close_price=out_close,
        return_1d=out_r1d,
        return_30d=out_r30d,
        return_120d=out_r120d,
        return_360d=out_r360d,
        sentiment_mean=sent_mean,
        sentiment_max=sent_max,
        sentiment_min=sent_min,
        num_articles=num_articles,
        num_pos_articles=num_pos,
        num_neg_articles=num_neg,
        pos_share=pos_share,
        neg_share=neg_share,
        prob_pos_mean=prob_pos_mean,
        prob_neg_mean=prob_neg_mean,
        prob_neu_mean=prob_neu_mean,
        prob_pos_max=prob_pos_max,
        prob_neg_max=prob_neg_max,
    )


# Stage 2: combine stock data with sentiment aggregates
AggregateStage = Stage(
    name="AggregateSentiment",
    input_schema=StockRowsArtifact,
    output_schema=SentimentAggregateArtifact,
    compute_fn=aggregate_sentiment,
)


# Trains XGBoost models for each return horizon
def run_xgboost_models(agg: SentimentAggregateArtifact) -> SentimentAggregateArtifact:
    logger.info("[XGBoost] Building dataset from sentiment snapshots")

    n = len(agg.ticker)
    if n == 0:
        agg.pred_return_1d = None
        agg.pred_return_30d = None
        agg.pred_return_120d = None
        agg.pred_return_360d = None
        return agg

    X_rows: List[List[float]] = []
    idxs: List[int] = []

    y_1d: List[float] = []
    y_30d: List[float] = []
    y_120d: List[float] = []
    y_360d: List[float] = []

    for i in range(n):
        if agg.return_1d[i] is None or agg.sentiment_mean[i] is None:
            continue

        feats = [
            _safe_num(agg.sentiment_mean[i]),
            _safe_num(agg.sentiment_max[i]),
            _safe_num(agg.sentiment_min[i]),
            float(agg.num_articles[i]) if agg.num_articles[i] is not None else 0.0,
            _safe_num(agg.pos_share[i]),
            _safe_num(agg.neg_share[i]),
            _safe_num(agg.prob_pos_mean[i]),
            _safe_num(agg.prob_neg_mean[i]),
            _safe_num(agg.prob_neu_mean[i]),
            _safe_num(agg.prob_pos_max[i]),
            _safe_num(agg.prob_neg_max[i]),
            _safe_num(agg.close_price[i]),
        ]

        X_rows.append(feats)
        idxs.append(i)

        y_1d.append(_safe_num(agg.return_1d[i]))
        y_30d.append(_safe_num(agg.return_30d[i]))
        y_120d.append(_safe_num(agg.return_120d[i]))
        y_360d.append(_safe_num(agg.return_360d[i]))

    if not X_rows:
        logger.info("[XGBoost] No usable rows with both sentiment and returns; skipping")
        agg.pred_return_1d = None
        agg.pred_return_30d = None
        agg.pred_return_120d = None
        agg.pred_return_360d = None
        return agg

    X = np.array(X_rows, dtype=float)
    y_1d_arr = np.array(y_1d, dtype=float)
    y_30d_arr = np.array(y_30d, dtype=float)
    y_120d_arr = np.array(y_120d, dtype=float)
    y_360d_arr = np.array(y_360d, dtype=float)

    logger.info(f"[XGBoost] Base training matrix: {X.shape[0]} rows x {X.shape[1]} features")

    force_cpu = _truthy_env("XGB_FORCE_CPU", "0")
    cuda_build = _xgb_has_cuda_build()
    prefer_gpu = (not force_cpu) and cuda_build

    # Builds one model with shared settings
    def make_model(device: str) -> XGBRegressor:
        return XGBRegressor(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            objective="reg:squarederror",
            n_jobs=4,
            tree_method="hist",
            device=device,
        )

    n_full = n

    # Trains and predicts one horizon at a time
    def _train_and_predict_per_horizon(y: np.ndarray, horizon_name: str) -> List[Optional[float]]:
        finite_mask = np.isfinite(y)
        num_used = int(finite_mask.sum())
        if num_used < 3:
            logger.warning(f"[XGBoost] Not enough finite labels for {horizon_name} (have {num_used}). Skipping.")
            return [None] * n_full

        X_clean = X[finite_mask]
        y_clean = y[finite_mask]

        model: Optional[XGBRegressor] = None
        trained_device = "cpu"

        if prefer_gpu:
            try:
                model = make_model("cuda")
                model.fit(X_clean, y_clean)
                trained_device = "cuda"
                logger.info(f"[XGBoost] Trained {horizon_name} model on GPU")
            except Exception as e:
                logger.warning(f"[XGBoost] GPU training failed for {horizon_name}; retrying on CPU: {e}")
                model = None

        if model is None:
            model = make_model("cpu")
            model.fit(X_clean, y_clean)
            trained_device = "cpu"
            logger.info(f"[XGBoost] Trained {horizon_name} model on CPU")

        if trained_device == "cuda":
            import xgboost as xgb
            preds_clean = model.get_booster().predict(xgb.DMatrix(X_clean))
        else:
            preds_clean = model.predict(X_clean)

        full_preds: List[Optional[float]] = [None] * n_full
        clean_idx = 0
        for row_in_X, used in enumerate(finite_mask):
            if not used:
                continue
            global_row = idxs[row_in_X]
            full_preds[global_row] = float(preds_clean[clean_idx])
            clean_idx += 1

        return full_preds

    agg.pred_return_1d = _train_and_predict_per_horizon(y_1d_arr, "1d")
    agg.pred_return_30d = _train_and_predict_per_horizon(y_30d_arr, "30d")
    agg.pred_return_120d = _train_and_predict_per_horizon(y_120d_arr, "120d")
    agg.pred_return_360d = _train_and_predict_per_horizon(y_360d_arr, "360d")

    logger.info("[XGBoost] Finished training and predictions")
    return agg


# Stage 3: generate predicted returns
XGBoostStage = Stage(
    name="XGBoostReturnModels",
    input_schema=SentimentAggregateArtifact,
    output_schema=SentimentAggregateArtifact,
    compute_fn=run_xgboost_models,
)


# Makes sure prediction columns exist before writing
def _ensure_snapshot_columns(cur) -> None:
    cur.execute("""
        ALTER TABLE sentiment_snapshots
        ADD COLUMN IF NOT EXISTS pred_return_1d DOUBLE PRECISION,
        ADD COLUMN IF NOT EXISTS pred_return_30d DOUBLE PRECISION,
        ADD COLUMN IF NOT EXISTS pred_return_120d DOUBLE PRECISION,
        ADD COLUMN IF NOT EXISTS pred_return_360d DOUBLE PRECISION;
    """)


_UPDATE_CLAUSE = """UPDATE SET
                close_price      = EXCLUDED.close_price,
                return_1d        = EXCLUDED.return_1d,
                return_30d       = EXCLUDED.return_30d,
                return_120d      = EXCLUDED.return_120d,
                return_360d      = EXCLUDED.return_360d,
                sentiment_mean   = EXCLUDED.sentiment_mean,
                sentiment_max    = EXCLUDED.sentiment_max,
                sentiment_min    = EXCLUDED.sentiment_min,
                num_articles     = EXCLUDED.num_articles,
                num_pos_articles = EXCLUDED.num_pos_articles,
                num_neg_articles = EXCLUDED.num_neg_articles,
                pos_share        = EXCLUDED.pos_share,
                neg_share        = EXCLUDED.neg_share,
                prob_pos_mean    = EXCLUDED.prob_pos_mean,
                prob_neg_mean    = EXCLUDED.prob_neg_mean,
                prob_neu_mean    = EXCLUDED.prob_neu_mean,
                prob_pos_max     = EXCLUDED.prob_pos_max,
                prob_neg_max     = EXCLUDED.prob_neg_max,
                pred_return_1d   = EXCLUDED.pred_return_1d,
                pred_return_30d  = EXCLUDED.pred_return_30d,
                pred_return_120d = EXCLUDED.pred_return_120d,
                pred_return_360d = EXCLUDED.pred_return_360d"""

_SQL_SKIP = f"ON CONFLICT (ticker, snapshot_date) DO NOTHING"
_SQL_UPSERT = f"ON CONFLICT (ticker, snapshot_date) DO {_UPDATE_CLAUSE}"


# Writes the final snapshot rows to sentiment_snapshots
def write_snapshots_to_db(agg: SentimentAggregateArtifact) -> DBArtifact:
    skip_existing = _truthy_env("AGG_SKIP_EXISTING", "0")

    # AGG_SKIP_BEFORE_DATE: when set alongside AGG_SKIP_EXISTING=1, only skip rows
    # whose snapshot_date is strictly before this date — rows on or after this date
    # are always upserted. Use this to preserve stable historical data while still
    # refreshing recent rows where new articles (from Azure jobs) may have arrived.
    # Example: AGG_SKIP_BEFORE_DATE=2026-03-01
    skip_before_date: Optional[date] = None
    raw_cutoff = (os.getenv("AGG_SKIP_BEFORE_DATE") or "").strip()
    if skip_existing and raw_cutoff:
        try:
            skip_before_date = datetime.fromisoformat(raw_cutoff).date()
            logger.info(f"[WriteSnapshots] AGG_SKIP_BEFORE_DATE={skip_before_date}: skipping existing rows before this date, upserting the rest")
        except ValueError:
            logger.warning(f"[WriteSnapshots] Invalid AGG_SKIP_BEFORE_DATE={raw_cutoff!r}, ignoring")

    if skip_existing and skip_before_date is None:
        logger.info("[WriteSnapshots] AGG_SKIP_EXISTING=1: skipping all existing rows (DO NOTHING)")
    elif not skip_existing:
        logger.info("[WriteSnapshots] Upserting all rows (DO UPDATE)")

    n = len(agg.ticker)
    if n == 0:
        return DBArtifact(num_snapshots=0)

    pred_1d = agg.pred_return_1d if agg.pred_return_1d is not None else [None] * n
    pred_30d = agg.pred_return_30d if agg.pred_return_30d is not None else [None] * n
    pred_120d = agg.pred_return_120d if agg.pred_return_120d is not None else [None] * n
    pred_360d = agg.pred_return_360d if agg.pred_return_360d is not None else [None] * n

    dsn = _get_dsn()
    conn = psycopg2.connect(dsn)
    cur = conn.cursor()
    _ensure_snapshot_columns(cur)

    num_written = 0

    rows = zip(
        agg.ticker,
        agg.snapshot_date,
        agg.close_price,
        agg.return_1d,
        agg.return_30d,
        agg.return_120d,
        agg.return_360d,
        agg.sentiment_mean,
        agg.sentiment_max,
        agg.sentiment_min,
        agg.num_articles,
        agg.num_pos_articles,
        agg.num_neg_articles,
        agg.pos_share,
        agg.neg_share,
        agg.prob_pos_mean,
        agg.prob_neg_mean,
        agg.prob_neu_mean,
        agg.prob_pos_max,
        agg.prob_neg_max,
        pred_1d,
        pred_30d,
        pred_120d,
        pred_360d,
    )

    for row in rows:
        (
            ticker, snapshot_date, close_price, return_1d, return_30d, return_120d, return_360d,
            sentiment_mean, sentiment_max, sentiment_min, num_articles, num_pos_articles, num_neg_articles,
            pos_share, neg_share, prob_pos_mean, prob_neg_mean, prob_neu_mean, prob_pos_max, prob_neg_max,
            pred_return_1d, pred_return_30d, pred_return_120d, pred_return_360d
        ) = row

        # Pick whether this row should be skipped or updated
        if skip_existing:
            if skip_before_date is not None:
                row_date = _parse_date(snapshot_date) if isinstance(snapshot_date, str) else snapshot_date
                conflict_sql = _SQL_SKIP if row_date < skip_before_date else _SQL_UPSERT
            else:
                conflict_sql = _SQL_SKIP
        else:
            conflict_sql = _SQL_UPSERT

        cur.execute(
            f"""
            INSERT INTO sentiment_snapshots (
                ticker,
                snapshot_date,
                close_price,
                return_1d,
                return_30d,
                return_120d,
                return_360d,
                sentiment_mean,
                sentiment_max,
                sentiment_min,
                num_articles,
                num_pos_articles,
                num_neg_articles,
                pos_share,
                neg_share,
                prob_pos_mean,
                prob_neg_mean,
                prob_neu_mean,
                prob_pos_max,
                prob_neg_max,
                pred_return_1d,
                pred_return_30d,
                pred_return_120d,
                pred_return_360d
            )
            VALUES (
                %(ticker)s,
                %(snapshot_date)s,
                %(close_price)s,
                %(return_1d)s,
                %(return_30d)s,
                %(return_120d)s,
                %(return_360d)s,
                %(sentiment_mean)s,
                %(sentiment_max)s,
                %(sentiment_min)s,
                %(num_articles)s,
                %(num_pos_articles)s,
                %(num_neg_articles)s,
                %(pos_share)s,
                %(neg_share)s,
                %(prob_pos_mean)s,
                %(prob_neg_mean)s,
                %(prob_neu_mean)s,
                %(prob_pos_max)s,
                %(prob_neg_max)s,
                %(pred_return_1d)s,
                %(pred_return_30d)s,
                %(pred_return_120d)s,
                %(pred_return_360d)s
            )
            {conflict_sql}
            """,
            {
                "ticker": ticker,
                "snapshot_date": snapshot_date,
                "close_price": close_price,
                "return_1d": return_1d,
                "return_30d": return_30d,
                "return_120d": return_120d,
                "return_360d": return_360d,
                "sentiment_mean": sentiment_mean,
                "sentiment_max": sentiment_max,
                "sentiment_min": sentiment_min,
                "num_articles": num_articles,
                "num_pos_articles": num_pos_articles,
                "num_neg_articles": num_neg_articles,
                "pos_share": pos_share,
                "neg_share": neg_share,
                "prob_pos_mean": prob_pos_mean,
                "prob_neg_mean": prob_neg_mean,
                "prob_neu_mean": prob_neu_mean,
                "prob_pos_max": prob_pos_max,
                "prob_neg_max": prob_neg_max,
                "pred_return_1d": pred_return_1d,
                "pred_return_30d": pred_return_30d,
                "pred_return_120d": pred_return_120d,
                "pred_return_360d": pred_return_360d,
            },
        )
        num_written += 1
        if num_written % 5000 == 0:
            logger.info(f"[WriteSnapshots] Upserted {num_written} rows...")
            conn.commit()

    conn.commit()
    cur.close()
    conn.close()

    logger.info(f"[WriteSnapshots] Wrote/updated {num_written} snapshot rows")
    return DBArtifact(num_snapshots=num_written)


# Stage 4: save snapshot rows back to the database
WriteSnapshotsStage = Stage(
    name="WriteSnapshots",
    input_schema=SentimentAggregateArtifact,
    output_schema=DBArtifact,
    compute_fn=write_snapshots_to_db,
)


# Full pipeline order
sentiment_snapshot_pipeline = Pipeline(
    "SentimentSnapshotAggregator",
    [
        LoadStocksStage,
        AggregateStage,
        XGBoostStage,
        WriteSnapshotsStage,
    ],
)


# Entry point that reads settings from env vars
def run_sentiment_snapshot_pipeline_from_env() -> Dict[str, Any]:
    tickers_env = (os.getenv("AGG_TICKERS") or "").strip()
    req = {
        "ticker": os.getenv("AGG_TICKER") or None,
        "tickers": [t.strip().upper() for t in tickers_env.split(",") if t.strip()] or None,
        "start_date": os.getenv("AGG_START_DATE") or None,
        "end_date": os.getenv("AGG_END_DATE") or None,
    }

    logger.info(f"[SnapshotPipeline] Running with request={req}")
    result = sentiment_snapshot_pipeline.run(req)
    logger.info(f"[SnapshotPipeline] Completed with result={result}")
    return result


# Run from the command line
if __name__ == "__main__":
    run_sentiment_snapshot_pipeline_from_env()
