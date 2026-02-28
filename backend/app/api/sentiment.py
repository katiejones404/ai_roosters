from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional, Literal
from decimal import InvalidOperation
import math

import sys
sys.path.insert(0, "/app")

from pydantic import BaseModel
from app.db.main import get_db

router = APIRouter(prefix="/sentiment", tags=["sentiment"])

SentimentLabel = Literal["bullish", "neutral", "bearish"]


class TimeRangeIndicators(BaseModel):
    d30: SentimentLabel
    d120: SentimentLabel
    d360: SentimentLabel


class GPTExplanations(BaseModel):
    d30: Optional[str] = None
    d120: Optional[str] = None
    d360: Optional[str] = None


class StockIndicatorsOut(BaseModel):
    id: str
    ticker: str
    snapshot_date: str
    close_price: Optional[float] = None
    indicators: TimeRangeIndicators
    explanations: Optional[GPTExplanations] = None
    gpt_model: Optional[str] = None
    gpt_generated_at: Optional[str] = None


def label_from_return(value: Optional[float]) -> SentimentLabel:
    if value is None:
        return "neutral"
    try:
        v = float(value)
    except (TypeError, ValueError, InvalidOperation):
        return "neutral"
    if math.isnan(v) or math.isinf(v):
        return "neutral"
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
    base_sql = """
        SELECT DISTINCT ON (ticker)
            id,
            ticker,
            snapshot_date,
            close_price,
            return_30d,
            return_120d,
            return_360d,
            gpt_expl_30d,
            gpt_expl_120d,
            gpt_expl_360d,
            gpt_model,
            gpt_generated_at
        FROM sentiment_snapshots
        {where_clause}
        ORDER BY ticker, snapshot_date DESC;
    """

    if ticker:
        sql = base_sql.format(where_clause="WHERE ticker ILIKE :ticker")
        rows = db.execute(text(sql), {"ticker": f"%{ticker}%"}).mappings().all()
    else:
        sql = base_sql.format(where_clause="")
        rows = db.execute(text(sql)).mappings().all()

    if not rows:
        return []

    results: List[StockIndicatorsOut] = []
    for row in rows:
        indicators = TimeRangeIndicators(
            d30=label_from_return(row.get("return_30d")),
            d120=label_from_return(row.get("return_120d")),
            d360=label_from_return(row.get("return_360d")),
        )

        expl_any = row.get("gpt_expl_30d") or row.get("gpt_expl_120d") or row.get("gpt_expl_360d")
        explanations = None
        if expl_any:
            explanations = GPTExplanations(
                d30=row.get("gpt_expl_30d"),
                d120=row.get("gpt_expl_120d"),
                d360=row.get("gpt_expl_360d"),
            )

        results.append(
            StockIndicatorsOut(
                id=str(row["id"]),
                ticker=row["ticker"],
                snapshot_date=str(row["snapshot_date"]),
                close_price=float(row["close_price"]) if row.get("close_price") is not None else None,
                indicators=indicators,
                explanations=explanations,
                gpt_model=row.get("gpt_model"),
                gpt_generated_at=str(row["gpt_generated_at"]) if row.get("gpt_generated_at") is not None else None,
            )
        )

    return results


@router.delete("/indicators/{ticker}")
def delete_ticker_indicators(ticker: str, db: Session = Depends(get_db)):
    sql = text("DELETE FROM sentiment_snapshots WHERE ticker = :ticker")
    result = db.execute(sql, {"ticker": ticker})
    db.commit()
    return {"status": "ok", "deleted": result.rowcount}