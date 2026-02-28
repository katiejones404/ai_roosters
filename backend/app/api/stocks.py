from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from datetime import date
from pydantic import BaseModel

from app.db.main import get_db

router = APIRouter(prefix="/stocks", tags=["stocks"])

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class StockSummary(BaseModel):
    ticker: str


class StockLatestRow(BaseModel):
    ticker: str
    date: date
    close: Optional[float] = None
    return_1d: Optional[float] = None
    return_30d: Optional[float] = None


class StockPriceRow(BaseModel):
    ticker: str
    date: date
    close: Optional[float] = None
    adjusted_close: Optional[float] = None
    return_1d: Optional[float] = None
    return_30d: Optional[float] = None
    return_120d: Optional[float] = None
    return_360d: Optional[float] = None


class SentimentSnapshotBase(BaseModel):
    snapshot_date: date
    close_price: Optional[float] = None
    return_1d: Optional[float] = None
    return_30d: Optional[float] = None
    return_120d: Optional[float] = None
    return_360d: Optional[float] = None
    sentiment_mean: Optional[float] = None
    sentiment_max: Optional[float] = None
    sentiment_min: Optional[float] = None
    num_articles: Optional[int] = None
    num_pos_articles: Optional[int] = None
    num_neg_articles: Optional[int] = None
    pos_share: Optional[float] = None
    neg_share: Optional[float] = None
    prob_pos_mean: Optional[float] = None
    prob_neg_mean: Optional[float] = None
    prob_neu_mean: Optional[float] = None
    prob_pos_max: Optional[float] = None
    prob_neg_max: Optional[float] = None


class SentimentSnapshotOut(SentimentSnapshotBase):
    id: str
    ticker: str


# ---------------------------------------------------------------------------
# Helpers (SQL snippets)
# ---------------------------------------------------------------------------

def _build_date_clause(start_date: Optional[date], end_date: Optional[date], params: dict) -> str:
    date_filters = []
    if start_date:
        date_filters.append("date >= :start_date")
        params["start_date"] = start_date
    if end_date:
        date_filters.append("date <= :end_date")
        params["end_date"] = end_date
    return (" AND " + " AND ".join(date_filters)) if date_filters else ""


# ---------------------------------------------------------------------------
# Stocks endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=List[StockSummary])
def list_stocks(db: Session = Depends(get_db)):
    """
    Return distinct tickers from the stocks table.
    Useful for dropdowns, dashboard filters, etc.
    """
    sql = text("""
        SELECT DISTINCT ticker
        FROM stocks
        ORDER BY ticker
    """)
    rows = db.execute(sql).mappings().all()
    return [StockSummary(ticker=row["ticker"]) for row in rows]


@router.get("/latest", response_model=List[StockLatestRow])
def get_all_latest_prices(db: Session = Depends(get_db)):
    """
    Return the single most-recent price row for every ticker in one query.

    IMPORTANT:
    - Computes return_1d and return_30d on-the-fly from price history using window functions.
    - Uses adjusted_close when available, else close.
    - Uses trading-row offsets (1 and ~21) rather than calendar days.
    """
    sql = text("""
        WITH priced AS (
            SELECT
                ticker,
                date,
                close,
                adjusted_close,
                COALESCE(adjusted_close, close) AS px
            FROM stocks
        ),
        with_lags AS (
            SELECT
                ticker,
                date,
                close,
                px,
                LAG(px, 1)  OVER (PARTITION BY ticker ORDER BY date) AS px_1,
                LAG(px, 21) OVER (PARTITION BY ticker ORDER BY date) AS px_21
            FROM priced
        ),
        computed AS (
            SELECT
                ticker,
                date,
                close,
                CASE
                    WHEN px_1 IS NULL OR px_1 = 0 THEN NULL
                    ELSE (px - px_1) / px_1
                END AS return_1d,
                CASE
                    WHEN px_21 IS NULL OR px_21 = 0 THEN NULL
                    ELSE (px - px_21) / px_21
                END AS return_30d
            FROM with_lags
        )
        SELECT DISTINCT ON (ticker)
            ticker, date, close, return_1d, return_30d
        FROM computed
        ORDER BY ticker, date DESC
    """)
    rows = db.execute(sql).mappings().all()

    return [
        StockLatestRow(
            ticker=row["ticker"],
            date=row["date"],
            close=float(row["close"]) if row["close"] is not None else None,
            return_1d=float(row["return_1d"]) if row["return_1d"] is not None else None,
            return_30d=float(row["return_30d"]) if row["return_30d"] is not None else None,
        )
        for row in rows
    ]


@router.get("/{ticker}/prices", response_model=List[StockPriceRow])
def get_stock_prices(
    ticker: str,
    start_date: Optional[date] = Query(None, description="Filter from this date (inclusive)"),
    end_date: Optional[date] = Query(None, description="Filter up to this date (inclusive)"),
    db: Session = Depends(get_db),
):
    """
    Return price history for a single ticker.

    IMPORTANT:
    - Computes return_1d/30d/120d/360d on-the-fly using window functions.
    - Uses adjusted_close when available, else close.
    - Uses trading-row offsets: 1 / 21 / 84 / 252 (approx 1d / 1m / 4m / 1y).
    - Keeps ORDER BY date ASC for charts.
    """
    params = {"ticker": ticker}
    date_clause = _build_date_clause(start_date, end_date, params)

    sql = text(f"""
        WITH priced AS (
            SELECT
                ticker,
                date,
                close,
                adjusted_close,
                COALESCE(adjusted_close, close) AS px
            FROM stocks
            WHERE ticker = :ticker
            {date_clause}
        ),
        with_lags AS (
            SELECT
                ticker,
                date,
                close,
                adjusted_close,
                px,
                LAG(px, 1)   OVER (PARTITION BY ticker ORDER BY date) AS px_1,
                LAG(px, 21)  OVER (PARTITION BY ticker ORDER BY date) AS px_21,
                LAG(px, 84)  OVER (PARTITION BY ticker ORDER BY date) AS px_84,
                LAG(px, 252) OVER (PARTITION BY ticker ORDER BY date) AS px_252
            FROM priced
        )
        SELECT
            ticker,
            date,
            close,
            adjusted_close,
            CASE WHEN px_1   IS NULL OR px_1   = 0 THEN NULL ELSE (px - px_1)   / px_1   END AS return_1d,
            CASE WHEN px_21  IS NULL OR px_21  = 0 THEN NULL ELSE (px - px_21)  / px_21  END AS return_30d,
            CASE WHEN px_84  IS NULL OR px_84  = 0 THEN NULL ELSE (px - px_84)  / px_84  END AS return_120d,
            CASE WHEN px_252 IS NULL OR px_252 = 0 THEN NULL ELSE (px - px_252) / px_252 END AS return_360d
        FROM with_lags
        ORDER BY date ASC
    """)

    rows = db.execute(sql, params).mappings().all()
    if not rows:
        raise HTTPException(status_code=404, detail="No price data found for this ticker")

    return [
        StockPriceRow(
            ticker=row["ticker"],
            date=row["date"],
            close=float(row["close"]) if row["close"] is not None else None,
            adjusted_close=float(row["adjusted_close"]) if row["adjusted_close"] is not None else None,
            return_1d=float(row["return_1d"]) if row["return_1d"] is not None else None,
            return_30d=float(row["return_30d"]) if row["return_30d"] is not None else None,
            return_120d=float(row["return_120d"]) if row["return_120d"] is not None else None,
            return_360d=float(row["return_360d"]) if row["return_360d"] is not None else None,
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Sentiment snapshot CRUD (per ticker)
# ---------------------------------------------------------------------------

@router.get("/{ticker}/snapshots", response_model=List[SentimentSnapshotOut])
def list_sentiment_snapshots(ticker: str, db: Session = Depends(get_db)):
    """
    List all sentiment_snapshots rows for a given ticker.
    Useful for debugging, admin tools, or a detailed sentiment history view.
    """
    sql = text("""
        SELECT
            id,
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
        FROM sentiment_snapshots
        WHERE ticker = :ticker
        ORDER BY snapshot_date DESC
    """)
    rows = db.execute(sql, {"ticker": ticker}).mappings().all()

    return [
        SentimentSnapshotOut(
            id=str(row["id"]),
            ticker=row["ticker"],
            snapshot_date=row["snapshot_date"],
            close_price=float(row["close_price"]) if row["close_price"] is not None else None,
            return_1d=float(row["return_1d"]) if row["return_1d"] is not None else None,
            return_30d=float(row["return_30d"]) if row["return_30d"] is not None else None,
            return_120d=float(row["return_120d"]) if row["return_120d"] is not None else None,
            return_360d=float(row["return_360d"]) if row["return_360d"] is not None else None,
            sentiment_mean=float(row["sentiment_mean"]) if row["sentiment_mean"] is not None else None,
            sentiment_max=float(row["sentiment_max"]) if row["sentiment_max"] is not None else None,
            sentiment_min=float(row["sentiment_min"]) if row["sentiment_min"] is not None else None,
            num_articles=row["num_articles"],
            num_pos_articles=row["num_pos_articles"],
            num_neg_articles=row["num_neg_articles"],
            pos_share=float(row["pos_share"]) if row["pos_share"] is not None else None,
            neg_share=float(row["neg_share"]) if row["neg_share"] is not None else None,
            prob_pos_mean=float(row["prob_pos_mean"]) if row["prob_pos_mean"] is not None else None,
            prob_neg_mean=float(row["prob_neg_mean"]) if row["prob_neg_mean"] is not None else None,
            prob_neu_mean=float(row["prob_neu_mean"]) if row["prob_neu_mean"] is not None else None,
            prob_pos_max=float(row["prob_pos_max"]) if row["prob_pos_max"] is not None else None,
            prob_neg_max=float(row["prob_neg_max"]) if row["prob_neg_max"] is not None else None,
        )
        for row in rows
    ]


@router.post("/{ticker}/snapshots", response_model=SentimentSnapshotOut)
def upsert_sentiment_snapshot(ticker: str, payload: SentimentSnapshotBase, db: Session = Depends(get_db)):
    """
    Create or update a sentiment_snapshots row for (ticker, snapshot_date).
    Requires a UNIQUE (ticker, snapshot_date) constraint on sentiment_snapshots.
    """
    sql = text("""
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
            :ticker,
            :snapshot_date,
            :close_price,
            :return_1d,
            :return_30d,
            :return_120d,
            :return_360d,
            :sentiment_mean,
            :sentiment_max,
            :sentiment_min,
            :num_articles,
            :num_pos_articles,
            :num_neg_articles,
            :pos_share,
            :neg_share,
            :prob_pos_mean,
            :prob_neg_mean,
            :prob_neu_mean,
            :prob_pos_max,
            :prob_neg_max
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
            prob_neg_max     = EXCLUDED.prob_neg_max
        RETURNING
            id,
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
    """)

    row = db.execute(
        sql,
        {
            "ticker": ticker,
            "snapshot_date": payload.snapshot_date,
            "close_price": payload.close_price,
            "return_1d": payload.return_1d,
            "return_30d": payload.return_30d,
            "return_120d": payload.return_120d,
            "return_360d": payload.return_360d,
            "sentiment_mean": payload.sentiment_mean,
            "sentiment_max": payload.sentiment_max,
            "sentiment_min": payload.sentiment_min,
            "num_articles": payload.num_articles,
            "num_pos_articles": payload.num_pos_articles,
            "num_neg_articles": payload.num_neg_articles,
            "pos_share": payload.pos_share,
            "neg_share": payload.neg_share,
            "prob_pos_mean": payload.prob_pos_mean,
            "prob_neg_mean": payload.prob_neg_mean,
            "prob_neu_mean": payload.prob_neu_mean,
            "prob_pos_max": payload.prob_pos_max,
            "prob_neg_max": payload.prob_neg_max,
        },
    ).mappings().first()
    db.commit()

    if not row:
        raise HTTPException(status_code=500, detail="Failed to upsert sentiment snapshot")

    return SentimentSnapshotOut(
        id=str(row["id"]),
        ticker=row["ticker"],
        snapshot_date=row["snapshot_date"],
        close_price=float(row["close_price"]) if row["close_price"] is not None else None,
        return_1d=float(row["return_1d"]) if row["return_1d"] is not None else None,
        return_30d=float(row["return_30d"]) if row["return_30d"] is not None else None,
        return_120d=float(row["return_120d"]) if row["return_120d"] is not None else None,
        return_360d=float(row["return_360d"]) if row["return_360d"] is not None else None,
        sentiment_mean=float(row["sentiment_mean"]) if row["sentiment_mean"] is not None else None,
        sentiment_max=float(row["sentiment_max"]) if row["sentiment_max"] is not None else None,
        sentiment_min=float(row["sentiment_min"]) if row["sentiment_min"] is not None else None,
        num_articles=row["num_articles"],
        num_pos_articles=row["num_pos_articles"],
        num_neg_articles=row["num_neg_articles"],
        pos_share=float(row["pos_share"]) if row["pos_share"] is not None else None,
        neg_share=float(row["neg_share"]) if row["neg_share"] is not None else None,
        prob_pos_mean=float(row["prob_pos_mean"]) if row["prob_pos_mean"] is not None else None,
        prob_neg_mean=float(row["prob_neg_mean"]) if row["prob_neg_mean"] is not None else None,
        prob_neu_mean=float(row["prob_neu_mean"]) if row["prob_neu_mean"] is not None else None,
        prob_pos_max=float(row["prob_pos_max"]) if row["prob_pos_max"] is not None else None,
        prob_neg_max=float(row["prob_neg_max"]) if row["prob_neg_max"] is not None else None,
    )


@router.delete("/{ticker}/snapshots/{snapshot_date}")
def delete_sentiment_snapshot(ticker: str, snapshot_date: date, db: Session = Depends(get_db)):
    """
    Delete a single sentiment_snapshots row identified by (ticker, snapshot_date).
    """
    sql = text("""
        DELETE FROM sentiment_snapshots
        WHERE ticker = :ticker
          AND snapshot_date = :snapshot_date
    """)
    result = db.execute(sql, {"ticker": ticker, "snapshot_date": snapshot_date})
    db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    return {"status": "ok"}