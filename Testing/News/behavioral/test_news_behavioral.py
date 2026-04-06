"""
test_news_behavioral.py - BEHAVIORAL TESTS
Behavioral / end-to-end API tests for the news endpoints.

Notes
-----
• Neither /articles/sentiment/summary or /articles requires authentication.
• /articles/sentiment/summary uses a module-level SQLAlchemy engine that is
  replaced with a MagicMock via patch.object() to avoid a real DB connection.
• /articles uses the injected get_db session; that dependency is overridden
  with a mock session whose query chain returns controlled FakeArticleRow
  objects, bypassing the PostgreSQL UUID type incompatibility in SQLite.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Import path setup
# ---------------------------------------------------------------------------

def _configure_paths() -> None:
    here = os.path.abspath(os.path.dirname(__file__))
    repo_root = os.path.abspath(os.path.join(here, "..", "..", "..", ".."))
    backend_root = os.path.join(repo_root, "backend")
    for candidate in ("/app", backend_root, repo_root):
        if os.path.isdir(candidate) and candidate not in sys.path:
            sys.path.insert(0, candidate)


_configure_paths()

from app.db.main import get_db          # noqa: E402
from app.api import news as news_module  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_engine(rows):
    """Return a mock SQLAlchemy engine whose connect() yields *rows* via fetchall()."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = rows

    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
    mock_ctx.__exit__ = MagicMock(return_value=False)

    mock_engine = MagicMock()
    mock_engine.connect.return_value = mock_ctx
    return mock_engine


class FakeArticleRow:
    """Mimics a StockNewsArticle ORM row without requiring PostgreSQL types."""

    def __init__(
        self,
        ticker: str = "AAPL",
        url: str = "https://example.com/news/1",
        title: str | None = "Test Headline",
        source: str | None = "TestSource",
        description: str | None = "A test description.",
        image_url: str | None = None,
        published_at: datetime | None = None,
        relevance_score: float | None = 0.85,
    ):
        self.id = uuid.uuid4()
        self.ticker = ticker
        self.url = url
        self.title = title
        self.source = source
        self.description = description
        self.image_url = image_url
        self.published_at = published_at or datetime(2024, 6, 1, 12, 0, 0)
        self.relevance_score = relevance_score


def _make_mock_db(rows):
    """
    Return a mock Session whose full ORM query chain
    (.filter = .order_by = .offset = .limit = .all) returns *rows*.
    """
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = rows

    mock_db = MagicMock()
    mock_db.query.return_value = mock_query
    return mock_db


def _build_app(db_rows=None):
    """Construct a minimal FastAPI app with the news router included."""
    app = FastAPI()
    app.include_router(news_module.router, prefix="/api")
    if db_rows is not None:
        def _override_get_db():
            yield _make_mock_db(db_rows)
        app.dependency_overrides[get_db] = _override_get_db
    return app


SUMMARY_URL = "/api/articles/sentiment/summary"
ARTICLES_URL = "/api/articles"


# ===========================================================================
# BEHAVIORAL: Sentiment summary endpoint
# ===========================================================================

class TestSentimentSummaryEndpoint:
    """Tests for GET /articles/sentiment/summary."""

    def _get(self, rows, params: str = ""):
        app = _build_app()
        with patch.object(news_module, "engine", _make_mock_engine(rows)):
            return TestClient(app).get(f"{SUMMARY_URL}{params}")

    def test_returns_200(self):
        res = self._get([("positive", 5)])
        assert res.status_code == 200

    def test_response_has_required_keys(self):
        data = self._get([]).json()
        assert {"total", "positive", "negative", "neutral", "unknown"} <= set(data.keys())

    def test_counts_aggregated_correctly(self):
        rows = [("positive", 50), ("negative", 20), ("neutral", 10), (None, 5)]
        data = self._get(rows).json()
        assert data["positive"] == 50
        assert data["negative"] == 20
        assert data["neutral"] == 10
        assert data["unknown"] == 5
        assert data["total"] == 85

    def test_empty_db_returns_all_zeros(self):
        data = self._get([]).json()
        assert data["total"] == 0
        assert data["positive"] == 0
        assert data["negative"] == 0
        assert data["neutral"] == 0
        assert data["unknown"] == 0

    def test_abbreviated_labels_normalized(self):
        rows = [("pos", 30), ("neg", 20), ("neu", 10)]
        data = self._get(rows).json()
        assert data["positive"] == 30
        assert data["negative"] == 20
        assert data["neutral"] == 10

    def test_none_sentiment_counted_as_unknown(self):
        rows = [(None, 7)]
        data = self._get(rows).json()
        assert data["unknown"] == 7

    def test_unrecognized_label_counted_as_unknown(self):
        rows = [("junk", 3)]
        data = self._get(rows).json()
        assert data["unknown"] == 3

    def test_start_query_param_accepted(self):
        res = self._get([], "?start=2024-01-01")
        assert res.status_code == 200

    def test_end_query_param_accepted(self):
        res = self._get([], "?end=2024-12-31")
        assert res.status_code == 200

    def test_start_and_end_params_accepted(self):
        res = self._get([], "?start=2024-01-01&end=2024-12-31")
        assert res.status_code == 200

    def test_total_equals_sum_of_buckets(self):
        rows = [("pos", 10), ("neg", 5), ("neu", 3), (None, 2)]
        data = self._get(rows).json()
        assert data["total"] == data["positive"] + data["negative"] + data["neutral"] + data["unknown"]

    def test_mixed_case_labels_normalized(self):
        rows = [("POSITIVE", 15), ("NEGative", 8)]
        data = self._get(rows).json()
        assert data["positive"] == 15
        assert data["negative"] == 8

    def test_same_label_accumulated_across_rows(self):
        rows = [("positive", 40), ("pos", 60)]
        data = self._get(rows).json()
        assert data["positive"] == 100


# ===========================================================================
# BEHAVIORAL: News articles list endpoint
# ===========================================================================

class TestNewsArticlesEndpoint:
    """Tests for GET /articles."""

    def _client(self, rows=None):
        return TestClient(_build_app(db_rows=rows or []))

    def test_returns_200_with_list(self):
        res = self._client([FakeArticleRow()]).get(ARTICLES_URL)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_empty_db_returns_empty_list(self):
        res = self._client([]).get(ARTICLES_URL)
        assert res.status_code == 200
        assert res.json() == []

    def test_article_contains_required_fields(self):
        row = FakeArticleRow(ticker="AAPL", title="Big News")
        data = self._client([row]).get(ARTICLES_URL).json()
        assert len(data) == 1
        article = data[0]
        for field in ("id", "ticker", "url", "title", "source"):
            assert field in article

    def test_ticker_value_returned_correctly(self):
        row = FakeArticleRow(ticker="NVDA")
        data = self._client([row]).get(ARTICLES_URL).json()
        assert data[0]["ticker"] == "NVDA"

    def test_title_value_returned_correctly(self):
        row = FakeArticleRow(title="Market Rally Today")
        data = self._client([row]).get(ARTICLES_URL).json()
        assert data[0]["title"] == "Market Rally Today"

    def test_relevance_score_returned(self):
        row = FakeArticleRow(relevance_score=0.92)
        data = self._client([row]).get(ARTICLES_URL).json()
        assert pytest.approx(data[0]["relevance_score"], rel=1e-3) == 0.92

    def test_relevance_score_none_returned_as_null(self):
        row = FakeArticleRow(relevance_score=None)
        data = self._client([row]).get(ARTICLES_URL).json()
        assert data[0]["relevance_score"] is None

    def test_published_at_none_returned_as_null(self):
        row = FakeArticleRow()
        row.published_at = None
        data = self._client([row]).get(ARTICLES_URL).json()
        assert data[0]["published_at"] is None

    def test_published_at_iso_format_when_present(self):
        row = FakeArticleRow(published_at=datetime(2024, 3, 15, 9, 30, 0))
        data = self._client([row]).get(ARTICLES_URL).json()
        assert "2024-03-15" in data[0]["published_at"]

    def test_multiple_articles_all_returned(self):
        rows = [FakeArticleRow(ticker="AAPL"), FakeArticleRow(ticker="TSLA")]
        data = self._client(rows).get(ARTICLES_URL).json()
        assert len(data) == 2
        tickers = {a["ticker"] for a in data}
        assert tickers == {"AAPL", "TSLA"}

    def test_ticker_query_param_accepted(self):
        res = self._client([FakeArticleRow(ticker="NVDA")]).get(f"{ARTICLES_URL}?ticker=NVDA")
        assert res.status_code == 200

    def test_limit_param_accepted(self):
        rows = [FakeArticleRow() for _ in range(5)]
        res = self._client(rows).get(f"{ARTICLES_URL}?limit=5")
        assert res.status_code == 200

    def test_offset_param_accepted(self):
        res = self._client([]).get(f"{ARTICLES_URL}?offset=10")
        assert res.status_code == 200

    def test_limit_zero_rejected_422(self):
        """limit must be >= 1."""
        res = self._client([]).get(f"{ARTICLES_URL}?limit=0")
        assert res.status_code == 422

    def test_limit_above_200_rejected_422(self):
        """limit must be <= 200."""
        res = self._client([]).get(f"{ARTICLES_URL}?limit=201")
        assert res.status_code == 422

    def test_negative_offset_rejected_422(self):
        """offset must be >= 0."""
        res = self._client([]).get(f"{ARTICLES_URL}?offset=-1")
        assert res.status_code == 422

    def test_limit_at_minimum_boundary(self):
        """limit=1 is the minimum valid value."""
        res = self._client([]).get(f"{ARTICLES_URL}?limit=1")
        assert res.status_code == 200

    def test_limit_at_maximum_boundary(self):
        """limit=200 is the maximum valid value."""
        res = self._client([]).get(f"{ARTICLES_URL}?limit=200")
        assert res.status_code == 200

    def test_id_is_a_string(self):
        """Article id is serialized as a string (UUID)."""
        row = FakeArticleRow()
        data = self._client([row]).get(ARTICLES_URL).json()
        assert isinstance(data[0]["id"], str)

    def test_all_optional_fields_can_be_none(self):
        """An article with all optional fields set to None doesn't crash the endpoint."""
        row = FakeArticleRow(
            title=None, source=None, description=None,
            image_url=None, relevance_score=None,
        )
        row.published_at = None
        data = self._client([row]).get(ARTICLES_URL).json()
        assert len(data) == 1
        assert data[0]["title"] is None
        assert data[0]["source"] is None
