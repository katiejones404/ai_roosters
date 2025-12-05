from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from decimal import Decimal, InvalidOperation
import math

import sys
sys.path.insert(0, "/app")

from app.db.main import get_db
from app.schema.schemas import StockIndicatorsOut, TimeRangeIndicators, SentimentLabel

router = APIRouter(prefix="/api/sentiment", tags=["sentiment"])


def label_from_return(value: Optional[float]) -> SentimentLabel:
    """
    Map numeric return (possibly Decimal/NaN) to bullish / neutral / bearish.
    Thresholds can be tuned later.
    """
    if value is None:
        return "neutral"

    # Convert Decimal/NUMERIC and guard against NaN/inf
    try:
        v = float(value)
    except (TypeError, ValueError, InvalidOperation):
        return "neutral"

    if math.isnan(v) or math.isinf(v):
        return "neutral"

    # 2% thresholds
    if v > 0.02:
        return "bullish"
    if v < -0.02:
        return "bearish"
    return "neutral"



@router.get("/indicators", response_model=List[StockIndicatorsOut])
def get_sentiment_indicators(
    ticker: Optional[str] = Query(None, description="If provided, filter by ticker"),
    db: Session = Depends(get_db),
):
    """
    Return latest 30d/120d/360d indicators for each ticker.
    If `ticker` is provided, returns only that ticker.
    """

    base_sql = """
        SELECT DISTINCT ON (ticker)
            ticker,
            snapshot_date,
            close_price,
            return_30d,
            return_120d,
            return_360d
        FROM sentiment_snapshots
        {where_clause}
        ORDER BY ticker, snapshot_date DESC;
    """

    if ticker:
        sql = base_sql.format(where_clause="WHERE ticker = :ticker")
        rows = db.execute(text(sql), {"ticker": ticker}).fetchall()
    else:
        sql = base_sql.format(where_clause="")
        rows = db.execute(text(sql)).fetchall()

    # Debug: see how many rows we actually fetched
    print(f"[DEBUG] /api/sentiment/indicators fetched {len(rows)} rows")

    # If nothing found, just return [] instead of 404
    if not rows:
        return []

    results: List[StockIndicatorsOut] = []

    for row in rows:
        t = row["ticker"]
        snapshot_date = row["snapshot_date"]
        close_price = row["close_price"]
        r30 = row["return_30d"]
        r120 = row["return_120d"]
        r360 = row["return_360d"]

        indicators = TimeRangeIndicators(
            d30=label_from_return(r30),
            d120=label_from_return(r120),
            d360=label_from_return(r360),
        )

        results.append(
            StockIndicatorsOut(
                ticker=t,
                snapshot_date=snapshot_date,
                close_price=float(close_price) if close_price is not None else None,
                indicators=indicators,
            )
        )

    return results
