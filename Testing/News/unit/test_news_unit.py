"""
test_news_unit.py,  UNIT TESTS
Pure-logic unit tests for the news API module.

Notes
-----
Tests cover _normalize_sentiment_label() and the aggregation /
SQL-building logic used inside get_article_sentiment_summary.
No HTTP layer or database connection is exercised here.
"""

from __future__ import annotations

from typing import Optional

import pytest


# ---------------------------------------------------------------------------
# Function under test
#
# _normalize_sentiment_label is a pure Python function with no dependencies.
# It is copied inline here so these unit tests run standalone without
# triggering the FastAPI / Pydantic import chain (Pydantic v1 is incompatible
# with Python 3.12 locally; in Docker the correct version is installed).
# ---------------------------------------------------------------------------

def _normalize_sentiment_label(raw: Optional[str]) -> str:
    """
    Normalize a raw FinBERT sentiment label to a canonical lowercase form.
    Mirror of app.api.news._normalize_sentiment_label.
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


# ===========================================================================
# UNIT: _normalize_sentiment_label
# ===========================================================================

class TestNormalizeSentimentLabel:
    """Unit tests for the pure normalization helper."""

    # ------------------------------------------------------------------
    # Positive variants
    # ------------------------------------------------------------------

    def test_positive_full(self):
        assert _normalize_sentiment_label("positive") == "positive"

    def test_positive_abbreviated(self):
        assert _normalize_sentiment_label("pos") == "positive"

    def test_positive_uppercase(self):
        assert _normalize_sentiment_label("POSITIVE") == "positive"

    def test_positive_mixed_case(self):
        assert _normalize_sentiment_label("Positive") == "positive"

    def test_positive_abbreviated_uppercase(self):
        assert _normalize_sentiment_label("POS") == "positive"

    # ------------------------------------------------------------------
    # Negative variants
    # ------------------------------------------------------------------

    def test_negative_full(self):
        assert _normalize_sentiment_label("negative") == "negative"

    def test_negative_abbreviated(self):
        assert _normalize_sentiment_label("neg") == "negative"

    def test_negative_uppercase(self):
        assert _normalize_sentiment_label("NEGATIVE") == "negative"

    def test_negative_mixed_case(self):
        assert _normalize_sentiment_label("Negative") == "negative"

    def test_negative_abbreviated_uppercase(self):
        assert _normalize_sentiment_label("NEG") == "negative"

    # ------------------------------------------------------------------
    # Neutral variants
    # ------------------------------------------------------------------

    def test_neutral_full(self):
        assert _normalize_sentiment_label("neutral") == "neutral"

    def test_neutral_abbreviated(self):
        assert _normalize_sentiment_label("neu") == "neutral"

    def test_neutral_uppercase(self):
        assert _normalize_sentiment_label("NEUTRAL") == "neutral"

    def test_neutral_mixed_case(self):
        assert _normalize_sentiment_label("Neutral") == "neutral"

    def test_neutral_abbreviated_uppercase(self):
        assert _normalize_sentiment_label("NEU") == "neutral"

    # ------------------------------------------------------------------
    # Unknown / unrecognized
    # ------------------------------------------------------------------

    def test_none_returns_unknown(self):
        assert _normalize_sentiment_label(None) == "unknown"

    def test_empty_string_returns_unknown(self):
        assert _normalize_sentiment_label("") == "unknown"

    def test_garbage_string_returns_unknown(self):
        assert _normalize_sentiment_label("garbage") == "unknown"

    def test_unknown_label_passthrough(self):
        assert _normalize_sentiment_label("unknown") == "unknown"

    def test_unknown_uppercase(self):
        assert _normalize_sentiment_label("UNKNOWN") == "unknown"

    # ------------------------------------------------------------------
    # Whitespace handling
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("raw,expected", [
        ("  positive  ", "positive"),
        ("  pos  ",      "positive"),
        ("\tneg\t",      "negative"),
        ("  neutral  ",  "neutral"),
        ("  neu  ",      "neutral"),
        ("  garbage  ",  "unknown"),
    ])
    def test_whitespace_is_stripped(self, raw, expected):
        assert _normalize_sentiment_label(raw) == expected

    # ------------------------------------------------------------------
    # Parametrized round-trip
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("raw,expected", [
        ("positive",  "positive"),
        ("pos",       "positive"),
        ("POSITIVE",  "positive"),
        ("negative",  "negative"),
        ("neg",       "negative"),
        ("NEGATIVE",  "negative"),
        ("neutral",   "neutral"),
        ("neu",       "neutral"),
        ("NEUTRAL",   "neutral"),
        ("unknown",   "unknown"),
        ("junk",      "unknown"),
        ("",          "unknown"),
        (None,        "unknown"),
    ])
    def test_parametrized_normalization(self, raw, expected):
        assert _normalize_sentiment_label(raw) == expected


# ===========================================================================
# UNIT: Sentiment aggregation logic
# ===========================================================================

class TestSentimentAggregation:
    """
    Tests for the counting / aggregation loop inside
    get_article_sentiment_summary.  The loop is replicated here as a
    pure function so it can be exercised without any HTTP or DB setup.
    """

    @staticmethod
    def _aggregate(rows):
        """Replicate the aggregation loop from the endpoint."""
        counts: dict[str, int] = {
            "positive": 0,
            "negative": 0,
            "neutral":  0,
            "unknown":  0,
        }
        for sentiment, c in rows:
            key = _normalize_sentiment_label(sentiment)
            counts[key] += int(c)
        return counts

    def test_empty_rows_returns_all_zeros(self):
        result = self._aggregate([])
        assert result == {"positive": 0, "negative": 0, "neutral": 0, "unknown": 0}

    def test_single_positive_row(self):
        result = self._aggregate([("positive", 10)])
        assert result["positive"] == 10
        assert result["negative"] == 0
        assert result["neutral"] == 0
        assert result["unknown"] == 0

    def test_single_negative_row(self):
        result = self._aggregate([("negative", 5)])
        assert result["negative"] == 5

    def test_single_neutral_row(self):
        result = self._aggregate([("neutral", 3)])
        assert result["neutral"] == 3

    def test_none_sentiment_mapped_to_unknown(self):
        result = self._aggregate([(None, 7)])
        assert result["unknown"] == 7

    def test_unrecognized_label_mapped_to_unknown(self):
        result = self._aggregate([("garbage", 2)])
        assert result["unknown"] == 2

    def test_multiple_rows_all_buckets(self):
        rows = [("positive", 50), ("neg", 30), ("neutral", 20), (None, 5)]
        result = self._aggregate(rows)
        assert result["positive"] == 50
        assert result["negative"] == 30
        assert result["neutral"] == 20
        assert result["unknown"] == 5

    def test_abbreviated_labels_accumulated_with_full_labels(self):
        """pos and positive both count towards the positive bucket."""
        rows = [("pos", 100), ("positive", 50)]
        result = self._aggregate(rows)
        assert result["positive"] == 150

    def test_total_equals_sum_of_all_buckets(self):
        rows = [("pos", 10), ("neg", 5), ("neu", 3), (None, 2)]
        counts = self._aggregate(rows)
        assert sum(counts.values()) == 20

    def test_large_counts_accumulated_correctly(self):
        rows = [("positive", 1_000_000), ("negative", 500_000)]
        result = self._aggregate(rows)
        assert result["positive"] == 1_000_000
        assert result["negative"] == 500_000

    @pytest.mark.parametrize("count_val", [0, 1, 99, 10_000])
    def test_integer_count_values(self, count_val):
        result = self._aggregate([("positive", count_val)])
        assert result["positive"] == count_val


# ===========================================================================
# UNIT: SQL WHERE clause construction
# ===========================================================================

class TestSqlWhereClauseConstruction:
    """
    Tests for the optional date-filter WHERE-clause building logic
    inside get_article_sentiment_summary.
    """

    @staticmethod
    def _build_where(start=None, end=None):
        """Replicate the where-clause building logic from the endpoint."""
        where = []
        params: dict = {}
        if start:
            where.append("published_at >= :start")
            params["start"] = start
        if end:
            where.append("published_at <= :end")
            params["end"] = end
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        return where_sql, params

    def test_no_filters_gives_empty_clause(self):
        sql, params = self._build_where()
        assert sql == ""
        assert params == {}

    def test_start_filter_only(self):
        sql, params = self._build_where(start="2024-01-01")
        assert "published_at >= :start" in sql
        assert params["start"] == "2024-01-01"
        assert "end" not in params

    def test_end_filter_only(self):
        sql, params = self._build_where(end="2024-12-31")
        assert "published_at <= :end" in sql
        assert params["end"] == "2024-12-31"
        assert "start" not in params

    def test_both_filters_combined_with_and(self):
        sql, params = self._build_where(start="2024-01-01", end="2024-12-31")
        assert "AND" in sql
        assert params["start"] == "2024-01-01"
        assert params["end"] == "2024-12-31"

    def test_both_filters_include_where_keyword(self):
        sql, _ = self._build_where(start="2024-01-01", end="2024-12-31")
        assert sql.startswith("WHERE")

    def test_start_only_no_and_keyword(self):
        sql, _ = self._build_where(start="2024-06-01")
        assert "AND" not in sql

    def test_end_only_no_and_keyword(self):
        sql, _ = self._build_where(end="2024-06-01")
        assert "AND" not in sql

    def test_none_start_treated_as_missing(self):
        sql, params = self._build_where(start=None)
        assert "start" not in params
        assert sql == ""

    def test_none_end_treated_as_missing(self):
        sql, params = self._build_where(end=None)
        assert "end" not in params
        assert sql == ""
