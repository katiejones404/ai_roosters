from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Dict, List, Optional, Literal
from decimal import InvalidOperation
import math

import sys
sys.path.insert(0, "/app")

from pydantic import BaseModel
from app.db.main import get_db

router = APIRouter(prefix="/sentiment", tags=["sentiment"])

WEBSITE_TICKERS: List[str] = [
    "KSS", "ALK", "NVS", "AXP", "FCX",
    "CSX", "DAL", "NTAP", "MRK", "COP",
    "BHP", "EA",
    "TSLA", "NVDA", "AAPL", "MSFT", "AMZN",
    "AMD", "META", "GOOGL", "GOOG", "PLTR",
    "MU", "NFLX",
    "NKE", "AAL", "BAC", "F", "INTC", "XOM", "T",
    "SOFI", "PLUG", "MARA", "SNAP", "COIN", "AMC", "RIVN", "CCL", "ENPH",
]
TICKER_ORDER: Dict[str, int] = {ticker: idx for idx, ticker in enumerate(WEBSITE_TICKERS)}
TICKER_SQL_LIST = ", ".join(f"'{ticker}'" for ticker in WEBSITE_TICKERS)

SentimentLabel = Literal["bullish", "neutral", "bearish"]


class TimeRangeIndicators(BaseModel):
    d30: SentimentLabel
    d120: SentimentLabel
    d360: SentimentLabel


class StockIndicatorsOut(BaseModel):
    id: str
    ticker: str
    snapshot_date: str
    close_price: Optional[float] = None
    indicators: TimeRangeIndicators


class NewsExplanationWindow(BaseModel):
    window_days: int
    article_count: int
    latest_article_at: Optional[str] = None
    summary_text: str


class StockNewsExplanationsOut(BaseModel):
    ticker: str
    d7: Optional[NewsExplanationWindow] = None
    d30: Optional[NewsExplanationWindow] = None
    preferred_window_days: Optional[int] = None
    preferred_summary_text: Optional[str] = None
    gpt_model: Optional[str] = None
    gpt_generated_at: Optional[str] = None


class StockOverviewOut(BaseModel):
    id: str
    ticker: str
    snapshot_date: str
    close_price: Optional[float] = None
    indicators: TimeRangeIndicators
    news_explanations: Optional[StockNewsExplanationsOut] = None


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


def sort_by_website_order(rows: List[dict]) -> List[dict]:
    return sorted(rows, key=lambda row: (TICKER_ORDER.get(row["ticker"], 10_000), row["ticker"]))


@router.get("/indicators", response_model=List[StockIndicatorsOut])
def get_sentiment_indicators(
    ticker: Optional[str] = Query(None, description="If provided, filter by ticker"),
    db: Session = Depends(get_db),
):
    where_clauses = [f"ticker IN ({TICKER_SQL_LIST})"]
    params = {}
    if ticker:
        where_clauses.append("ticker ILIKE :ticker")
        params["ticker"] = f"%{ticker}%"

    sql = f"""
        SELECT DISTINCT ON (ticker)
            id,
            ticker,
            snapshot_date,
            close_price,
            return_30d,
            return_120d,
            return_360d
        FROM sentiment_snapshots
        WHERE {' AND '.join(where_clauses)}
        ORDER BY ticker, snapshot_date DESC;
    """

    rows = db.execute(text(sql), params).mappings().all()
    if not rows:
        return []

    results: List[StockIndicatorsOut] = []
    for row in sort_by_website_order([dict(r) for r in rows]):
        indicators = TimeRangeIndicators(
            d30=label_from_return(row.get("return_30d")),
            d120=label_from_return(row.get("return_120d")),
            d360=label_from_return(row.get("return_360d")),
        )
        results.append(
            StockIndicatorsOut(
                id=str(row["id"]),
                ticker=row["ticker"],
                snapshot_date=str(row["snapshot_date"]),
                close_price=float(row["close_price"]) if row.get("close_price") is not None else None,
                indicators=indicators,
            )
        )

    return results


@router.get("/news-explanations", response_model=List[StockNewsExplanationsOut])
def get_news_explanations(
    ticker: Optional[str] = Query(None, description="If provided, filter by ticker"),
    db: Session = Depends(get_db),
):
    where_clauses = [f"ticker IN ({TICKER_SQL_LIST})", "window_days IN (7, 30)"]
    params = {}
    if ticker:
        where_clauses.append("ticker ILIKE :ticker")
        params["ticker"] = f"%{ticker}%"

    sql = f"""
        SELECT DISTINCT ON (ticker, window_days)
            ticker,
            window_days,
            article_count,
            latest_article_at,
            summary_text,
            model,
            generated_at
        FROM stock_news_summaries
        WHERE {' AND '.join(where_clauses)}
        ORDER BY ticker, window_days, generated_at DESC;
    """

    rows = [dict(row) for row in db.execute(text(sql), params).mappings().all()]
    if not rows:
        return []

    grouped: Dict[str, StockNewsExplanationsOut] = {}
    for row in rows:
        ticker_value = row["ticker"]
        explanation = grouped.get(ticker_value)
        if explanation is None:
            explanation = StockNewsExplanationsOut(
                ticker=ticker_value,
                d7=None,
                d30=None,
                preferred_window_days=None,
                preferred_summary_text=None,
                gpt_model=row.get("model"),
                gpt_generated_at=str(row["generated_at"]) if row.get("generated_at") is not None else None,
            )
            grouped[ticker_value] = explanation

        window = NewsExplanationWindow(
            window_days=int(row["window_days"]),
            article_count=int(row.get("article_count") or 0),
            latest_article_at=str(row["latest_article_at"]) if row.get("latest_article_at") is not None else None,
            summary_text=row.get("summary_text") or "No recent stock-specific articles were found for this window.",
        )

        if window.window_days == 7:
            explanation.d7 = window
        elif window.window_days == 30:
            explanation.d30 = window

        # Keep the freshest metadata seen for the ticker.
        if row.get("generated_at") is not None:
            explanation.gpt_generated_at = str(row["generated_at"])
        if row.get("model"):
            explanation.gpt_model = row["model"]

    results = list(grouped.values())
    for item in results:
        preferred = None
        if item.d7 and item.d7.article_count > 0:
            preferred = item.d7
        elif item.d30 and item.d30.article_count > 0:
            preferred = item.d30
        elif item.d7 is not None:
            preferred = item.d7
        elif item.d30 is not None:
            preferred = item.d30

        if preferred is not None:
            item.preferred_window_days = preferred.window_days
            item.preferred_summary_text = preferred.summary_text

    return sorted(results, key=lambda item: (TICKER_ORDER.get(item.ticker, 10_000), item.ticker))


@router.get("/overview", response_model=List[StockOverviewOut])
def get_stock_overview(
    ticker: Optional[str] = Query(None, description="If provided, filter by ticker"),
    db: Session = Depends(get_db),
):
    indicator_rows = get_sentiment_indicators(ticker=ticker, db=db)
    explanation_rows = get_news_explanations(ticker=ticker, db=db)
    explanation_map = {row.ticker: row for row in explanation_rows}

    results: List[StockOverviewOut] = []
    for row in indicator_rows:
        results.append(
            StockOverviewOut(
                id=row.id,
                ticker=row.ticker,
                snapshot_date=row.snapshot_date,
                close_price=row.close_price,
                indicators=row.indicators,
                news_explanations=explanation_map.get(row.ticker),
            )
        )

    return results


@router.delete("/indicators/{ticker}")
def delete_ticker_indicators(ticker: str, db: Session = Depends(get_db)):
    sql = text("DELETE FROM sentiment_snapshots WHERE ticker = :ticker")
    result = db.execute(sql, {"ticker": ticker})
    db.commit()
    return {"status": "ok", "deleted": result.rowcount}


@router.delete("/news-explanations/{ticker}")
def delete_ticker_news_explanations(ticker: str, db: Session = Depends(get_db)):
    sql = text("DELETE FROM stock_news_summaries WHERE ticker = :ticker")
    result = db.execute(sql, {"ticker": ticker})
    db.commit()
    return {"status": "ok", "deleted": result.rowcount}
