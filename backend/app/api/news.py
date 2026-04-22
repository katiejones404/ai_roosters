"""
News article API endpoints for retrieving stock news and sentiment summaries.

Notes
-----
Article sentiment counts come from the historical articles table scored by FinBERT.
Recent daily news is served from the stock_news_articles table populated by Marketaux.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.main import get_db
from app.models.models import Portfolio, StockNewsArticle, User

router = APIRouter()

# Use DATABASE_URL if provided; otherwise fall back to your compose defaults
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://stock_user:stock_pass@postgres:5432/stock_db",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


class ArticleSentimentSummary(BaseModel):
    total: int
    positive: int
    negative: int
    neutral: int
    unknown: int


def _normalize_sentiment_label(raw: Optional[str]) -> str:
    """
    Normalize a raw FinBERT sentiment label to a canonical lowercase form.

    Notes
    -----
    Accepts abbreviated forms such as 'pos', 'neg', 'neu' in addition to
    full forms. Any unrecognized value returns 'unknown'.
    """
    if not raw:
        return "unknown"
    s = raw.strip().lower()

    if s in {"pos", "positive"}:
        return "positive"
    if s in {"neg", "negative"}:
        return "negative"
    if s in {"neu", "neutral"}:
        return "neutral"

    return "unknown"


@router.get("/articles/sentiment/summary", response_model=ArticleSentimentSummary)
def get_article_sentiment_summary(
    start: Optional[str] = Query(
        default=None,
        description="Optional ISO date/time (inclusive), filters by published_at >= start",
    ),
    end: Optional[str] = Query(
        default=None,
        description="Optional ISO date/time (inclusive), filters by published_at <= end",
    ),
) -> ArticleSentimentSummary:
    """
    Returns global counts of article sentiments from the `articles` table.

    Uses `sentiment` text column (FinBERT label). Anything missing/unknown -> unknown.
    Optional start/end filter on published_at.
    """
    where = []
    params: Dict[str, object] = {}

    if start:
        where.append("published_at >= :start")
        params["start"] = start
    if end:
        where.append("published_at <= :end")
        params["end"] = end

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    sql = text(
        f"""
        SELECT sentiment, COUNT(*) AS c
        FROM articles
        {where_sql}
        GROUP BY sentiment
        """
    )

    counts = {"positive": 0, "negative": 0, "neutral": 0, "unknown": 0}

    with engine.connect() as conn:
        rows = conn.execute(sql, params).fetchall()

    for sentiment, c in rows:
        key = _normalize_sentiment_label(sentiment)
        counts[key] += int(c)

    total = sum(counts.values())
    return ArticleSentimentSummary(total=total, **counts)


class NewsArticleOut(BaseModel):
    id: str
    ticker: str
    url: str
    title: Optional[str]
    source: Optional[str]
    description: Optional[str]
    image_url: Optional[str]
    published_at: Optional[str]
    relevance_score: Optional[float]

    class Config:
        from_attributes = True


@router.get("/articles", response_model=List[NewsArticleOut])
def get_news_articles(
    ticker: Optional[str] = Query(default=None, description="Filter by ticker symbol"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[NewsArticleOut]:
    """
    Returns recent articles from stock_news_articles, newest first.

    News access is restricted to tickers currently held in the authenticated
    user's portfolio. If a ticker filter is provided and the user does not hold
    that ticker, an empty list is returned.
    """
    held_tickers = [
        row[0].upper()
        for row in db.query(Portfolio.ticker)
        .filter(Portfolio.user_id == current_user.id)
        .distinct()
        .all()
        if row[0]
    ]

    if not held_tickers:
        return []

    query = db.query(StockNewsArticle).filter(StockNewsArticle.ticker.in_(held_tickers))

    if ticker:
        normalized_ticker = ticker.upper()
        if normalized_ticker not in held_tickers:
            return []
        query = query.filter(StockNewsArticle.ticker == normalized_ticker)

    rows = (
        query.order_by(StockNewsArticle.published_at.desc().nulls_last())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        NewsArticleOut(
            id=str(row.id),
            ticker=row.ticker,
            url=row.url,
            title=row.title,
            source=row.source,
            description=row.description,
            image_url=row.image_url,
            published_at=row.published_at.isoformat() if row.published_at else None,
            relevance_score=float(row.relevance_score) if row.relevance_score is not None else None,
        )
        for row in rows
    ]