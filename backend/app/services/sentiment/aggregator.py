from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Callable, Type, Optional, Tuple
from datetime import date, datetime
import math

import psycopg2
import numpy as np
from xgboost import XGBRegressor

# --------------------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------------------

logger = logging.getLogger("snapshot_pipeline")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(_handler)

# --------------------------------------------------------------------------------------
# Pydantic BaseModel (with stub fallback)
# --------------------------------------------------------------------------------------

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


class Artifact(BaseModel):
    def to_json(self) -> Dict[str, Any]:
        if hasattr(self, "model_dump"):
            return self.model_dump()
        if hasattr(self, "dict"):
            return self.dict()
        return self.__dict__.copy()

# --------------------------------------------------------------------------------------
# Core Stage / Pipeline infra
# --------------------------------------------------------------------------------------

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

# --------------------------------------------------------------------------------------
# Artifacts
# --------------------------------------------------------------------------------------

class SnapshotRequestArtifact(Artifact):
    ticker: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class StockRowsArtifact(Artifact):
    ticker: List[str]
    date: List[str]  # "YYYY-MM-DD"
    close_price: List[Optional[float]]
    return_1d: List[Optional[float]]
    return_30d: List[Optional[float]]
    return_120d: List[Optional[float]]
    return_360d: List[Optional[float]]


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


class DBArtifact(Artifact):
    num_snapshots: int

# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------

def _get_dsn() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql://stock_user:stock_pass@postgres:5432/stock_db",
    )


def _parse_date(s: str) -> date:
    return datetime.fromisoformat(s).date()


def _mean(values: List[Optional[float]]) -> Optional[float]:
    nums = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    if not nums:
        return None
    return float(sum(nums) / len(nums))


def _safe_max(values: List[Optional[float]]) -> Optional[float]:
    nums = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    return max(nums) if nums else None


def _safe_min(values: List[Optional[float]]) -> Optional[float]:
    nums = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    return min(nums) if nums else None


def _truthy_env(name: str, default: str = "0") -> bool:
    val = os.getenv(name, default).strip().lower()
    return val in {"1", "true", "t", "yes", "y", "on"}


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


def _safe_num(x: Optional[float]) -> float:
    if x is None:
        return 0.0
    v = float(x)
    if not math.isfinite(v):
        return 0.0
    return v

# --------------------------------------------------------------------------------------
# Stage 1: Load stocks + returns
# --------------------------------------------------------------------------------------

def load_stock_rows(req: SnapshotRequestArtifact) -> StockRowsArtifact:
    logger.info("[LoadStocks] Fetching stock rows from database")

    dsn = _get_dsn()
    conn = psycopg2.connect(dsn)
    cur = conn.cursor()

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
        WHERE 1=1
    """
    params: List[Any] = []

    if req.ticker:
        sql += " AND ticker = %s"
        params.append(req.ticker)

    if req.start_date:
        sql += " AND date >= %s"
        params.append(req.start_date)

    if req.end_date:
        sql += " AND date <= %s"
        params.append(req.end_date)

    sql += " ORDER BY ticker, date"

    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    tickers: List[str] = []
    dates: List[str] = []
    close_price: List[Optional[float]] = []
    r1d: List[Optional[float]] = []
    r30d: List[Optional[float]] = []
    r120d: List[Optional[float]] = []
    r360d: List[Optional[float]] = []

    for (t, d, close, ret1, ret30, ret120, ret360) in rows:
        tickers.append(str(t))
        dates.append(d.isoformat() if isinstance(d, date) else str(d))
        close_price.append(float(close) if close is not None else None)
        r1d.append(float(ret1) if ret1 is not None else None)
        r30d.append(float(ret30) if ret30 is not None else None)
        r120d.append(float(ret120) if ret120 is not None else None)
        r360d.append(float(ret360) if ret360 is not None else None)

    logger.info(f"[LoadStocks] Loaded {len(tickers)} stock rows")

    return StockRowsArtifact(
        ticker=tickers,
        date=dates,
        close_price=close_price,
        return_1d=r1d,
        return_30d=r30d,
        return_120d=r120d,
        return_360d=r360d,
    )


LoadStocksStage = Stage(
    name="LoadStocks",
    input_schema=SnapshotRequestArtifact,
    output_schema=StockRowsArtifact,
    compute_fn=load_stock_rows,
)

# --------------------------------------------------------------------------------------
# Stage 2: Aggregate article sentiment per DATE (ALL articles apply to ALL stocks)
# --------------------------------------------------------------------------------------

def aggregate_sentiment(stocks: StockRowsArtifact) -> SentimentAggregateArtifact:
    """
    Build daily sentiment aggregates from articles by published_at::date,
    then attach those daily aggregates to every (ticker, stocks.date).
    """
    logger.info("[AggregateSentiment] Aggregating ALL-articles sentiment per day (published_at::date)")

    n = len(stocks.ticker)
    if n == 0:
        logger.info("[AggregateSentiment] No stock rows; returning empty artifact")
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

    logger.info(f"[AggregateSentiment] Stocks window: {min_date_val} -> {max_date_val}")

    dsn = _get_dsn()
    conn = psycopg2.connect(dsn)
    cur = conn.cursor()

    # Pull only the fields we need, grouped per day.
    # IMPORTANT: we count only rows that have a sentiment label and/or scores available.
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

    daily: Dict[date, Dict[str, Any]] = {}
    rows = cur.fetchall()
    cur.close()
    conn.close()

    logger.info(f"[AggregateSentiment] Loaded {len(rows)} daily sentiment rows from articles")

    for (
        pub_date,
        n_labeled,
        n_pos,
        n_neg,
        mean_score,
        max_score,
        min_score,
        pp_mean,
        pn_mean,
        pneu_mean,
        pp_max,
        pn_max,
    ) in rows:
        d = pub_date if isinstance(pub_date, date) else _parse_date(str(pub_date))
        nl = int(n_labeled or 0)
        np_ = int(n_pos or 0)
        nn_ = int(n_neg or 0)

        daily[d] = {
            "num_articles": nl,
            "num_pos_articles": np_,
            "num_neg_articles": nn_,
            "pos_share": (float(np_) / nl) if nl > 0 else None,
            "neg_share": (float(nn_) / nl) if nl > 0 else None,

            "sentiment_mean": float(mean_score) if mean_score is not None else None,
            "sentiment_max": float(max_score) if max_score is not None else None,
            "sentiment_min": float(min_score) if min_score is not None else None,

            "prob_pos_mean": float(pp_mean) if pp_mean is not None else None,
            "prob_neg_mean": float(pn_mean) if pn_mean is not None else None,
            "prob_neu_mean": float(pneu_mean) if pneu_mean is not None else None,

            "prob_pos_max": float(pp_max) if pp_max is not None else None,
            "prob_neg_max": float(pn_max) if pn_max is not None else None,
        }

    # Now attach daily stats to each stock row
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

    missing_days = 0

    for i in range(n):
        t = stocks.ticker[i]
        d = _parse_date(stocks.date[i])

        day = daily.get(d)
        if day is None:
            missing_days += 1
            # No articles that day -> fill zeros/None
            sent_mean.append(None)
            sent_max.append(None)
            sent_min.append(None)

            num_articles.append(0)
            num_pos.append(0)
            num_neg.append(0)
            pos_share.append(None)
            neg_share.append(None)

            prob_pos_mean.append(None)
            prob_neg_mean.append(None)
            prob_neu_mean.append(None)
            prob_pos_max.append(None)
            prob_neg_max.append(None)
        else:
            sent_mean.append(day["sentiment_mean"])
            sent_max.append(day["sentiment_max"])
            sent_min.append(day["sentiment_min"])

            num_articles.append(int(day["num_articles"]))
            num_pos.append(int(day["num_pos_articles"]))
            num_neg.append(int(day["num_neg_articles"]))
            pos_share.append(day["pos_share"])
            neg_share.append(day["neg_share"])

            prob_pos_mean.append(day["prob_pos_mean"])
            prob_neg_mean.append(day["prob_neg_mean"])
            prob_neu_mean.append(day["prob_neu_mean"])
            prob_pos_max.append(day["prob_pos_max"])
            prob_neg_max.append(day["prob_neg_max"])

        out_ticker.append(t)
        out_date.append(d.isoformat())
        out_close.append(stocks.close_price[i])
        out_r1d.append(stocks.return_1d[i])
        out_r30d.append(stocks.return_30d[i])
        out_r120d.append(stocks.return_120d[i])
        out_r360d.append(stocks.return_360d[i])

    logger.info(
        f"[AggregateSentiment] Built aggregates for {len(out_ticker)} snapshot rows "
        f"(days_missing_articles={missing_days})"
    )

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


AggregateStage = Stage(
    name="AggregateSentiment",
    input_schema=StockRowsArtifact,
    output_schema=SentimentAggregateArtifact,
    compute_fn=aggregate_sentiment,
)

# --------------------------------------------------------------------------------------
# Stage 3: XGBoost on returns using sentiment features
# --------------------------------------------------------------------------------------

def run_xgboost_models(agg: SentimentAggregateArtifact) -> SentimentAggregateArtifact:
    logger.info("[XGBoost] Building dataset from sentiment snapshots")

    n = len(agg.ticker)
    if n == 0:
        logger.info("[XGBoost] No rows; skipping model training")
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

    if force_cpu:
        logger.info("[XGBoost] XGB_FORCE_CPU=1 -> forcing CPU")
    elif cuda_build:
        logger.info("[XGBoost] CUDA-enabled XGBoost build detected; will try GPU first")
    else:
        logger.info("[XGBoost] XGBoost CUDA not available; using CPU")

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

    m = X.shape[0]
    n_full = n

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


XGBoostStage = Stage(
    name="XGBoostReturnModels",
    input_schema=SentimentAggregateArtifact,
    output_schema=SentimentAggregateArtifact,
    compute_fn=run_xgboost_models,
)

# --------------------------------------------------------------------------------------
# Stage 4: Write to sentiment_snapshots
# --------------------------------------------------------------------------------------

def write_snapshots_to_db(agg: SentimentAggregateArtifact) -> DBArtifact:
    logger.info("[WriteSnapshots] Writing sentiment snapshots to database")

    n = len(agg.ticker)
    if n == 0:
        logger.info("[WriteSnapshots] No snapshots to write")
        return DBArtifact(num_snapshots=0)

    dsn = _get_dsn()
    conn = psycopg2.connect(dsn)
    cur = conn.cursor()

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
    )

    for (
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
    ) in rows:
        cur.execute(
            """
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
                prob_neg_max
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
                %(prob_neg_max)s
            )
            ON CONFLICT (ticker, snapshot_date) DO UPDATE SET
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
                prob_neg_max     = EXCLUDED.prob_neg_max;
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


WriteSnapshotsStage = Stage(
    name="WriteSnapshots",
    input_schema=SentimentAggregateArtifact,
    output_schema=DBArtifact,
    compute_fn=write_snapshots_to_db,
)

# --------------------------------------------------------------------------------------
# Pipeline
# --------------------------------------------------------------------------------------

sentiment_snapshot_pipeline = Pipeline(
    "SentimentSnapshotAggregator",
    [
        LoadStocksStage,
        AggregateStage,
        XGBoostStage,
        WriteSnapshotsStage,
    ],
)

# --------------------------------------------------------------------------------------
# Public helper for FastAPI startup
# --------------------------------------------------------------------------------------

def run_sentiment_snapshot_pipeline_from_env() -> Dict[str, Any]:
    req = {
        "ticker": os.getenv("AGG_TICKER") or None,
        "start_date": os.getenv("AGG_START_DATE") or None,
        "end_date": os.getenv("AGG_END_DATE") or None,
    }

    logger.info(f"[SnapshotPipeline] Running with request={req}")
    result = sentiment_snapshot_pipeline.run(req)
    logger.info(f"[SnapshotPipeline] Completed with result={result}")
    return result

# --------------------------------------------------------------------------------------
# CLI entry point
# --------------------------------------------------------------------------------------

if __name__ == "__main__":
    run_sentiment_snapshot_pipeline_from_env()