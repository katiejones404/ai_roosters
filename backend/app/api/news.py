"""
News article API endpoints for retrieving stock news and sentiment summaries.
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
from app.models.models import StockNewsArticle, User

router = APIRouter()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://stock_user:stock_pass@postgres:5432/stock_db")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

class ArticleSentimentSummary(BaseModel):
    total: int
    positive: int
    negative: int
    neutral: int
    unknown: int

def _normalize_sentiment_label(raw: Optional[str]) -> str:
    """Map raw sentiment label variants (pos, positive, neg, negative, etc.) to a consistent string."""
    if not raw: return "unknown"
    s = raw.strip().lower()
    if s in {"pos", "positive"}: return "positive"
    if s in {"neg", "negative"}: return "negative"
    if s in {"neu", "neutral"}: return "neutral"
    return "unknown"

@router.get("/articles/sentiment/summary", response_model=ArticleSentimentSummary)
def get_article_sentiment_summary(
    start: Optional[str] = Query(default=None),
    end: Optional[str] = Query(default=None),
) -> ArticleSentimentSummary:
    """Return aggregate sentiment counts (positive, negative, neutral, unknown) across all articles, with optional date filtering."""
    where = []
    params: Dict[str, object] = {}
    if start:
        where.append("published_at >= :start"); params["start"] = start
    if end:
        where.append("published_at <= :end"); params["end"] = end
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    sql = text(f"SELECT sentiment, COUNT(*) AS c FROM articles {where_sql} GROUP BY sentiment")
    counts = {"positive": 0, "negative": 0, "neutral": 0, "unknown": 0}
    with engine.connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    for sentiment, c in rows:
        key = _normalize_sentiment_label(sentiment)
        counts[key] += int(c)
    return ArticleSentimentSummary(total=sum(counts.values()), **counts)

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
    ticker: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[NewsArticleOut]:
    """Return a paginated list of news articles, optionally filtered by ticker symbol."""
    query = db.query(StockNewsArticle)
    if ticker:
        query = query.filter(StockNewsArticle.ticker == ticker.strip().upper())
    rows = query.order_by(StockNewsArticle.published_at.desc().nulls_last()).offset(offset).limit(limit).all()
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