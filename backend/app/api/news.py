from __future__ import annotations

import os
from typing import Dict, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import create_engine, text

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
    if not raw:
        return "unknown"
    s = raw.strip().lower()

    # normalize common variants
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