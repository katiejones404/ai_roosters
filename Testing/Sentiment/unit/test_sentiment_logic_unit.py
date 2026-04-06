"""
test_sentiment_logic_unit.py  -  UNIT TESTS
Pure-logic unit tests for sentiment API functions.

Notes
-----
label_from_return and sort_by_website_order are inlined here because
app.api.sentiment imports FastAPI/Pydantic at module level, which is
incompatible with the local Python 3.12 + Pydantic v1 setup.
In Docker the originals are exercised by the behavioral tests.
"""
from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional

import pytest


# ---------------------------------------------------------------------------
# Inline implementations (mirrors of app.api.sentiment)
# ---------------------------------------------------------------------------

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
TICKER_ORDER: Dict[str, int] = {t: i for i, t in enumerate(WEBSITE_TICKERS)}


def label_from_return(value: Optional[float]) -> str:
    """Mirror of app.api.sentiment.label_from_return."""
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
    """Mirror of app.api.sentiment.sort_by_website_order."""
    return sorted(rows, key=lambda r: (TICKER_ORDER.get(r["ticker"], 10_000), r["ticker"]))


# ===========================================================================
# UNIT: label_from_return
# ===========================================================================

class TestLabelFromReturn:

    @pytest.mark.parametrize("value,expected", [
        (None,              "neutral"),
        ("not-a-number",    "neutral"),
        (float("nan"),      "neutral"),
        (float("inf"),      "neutral"),
        (-float("inf"),     "neutral"),
        (0.0,               "neutral"),
        (0.02,              "neutral"),
        (-0.02,             "neutral"),
        (0.0200001,         "bullish"),
        (-0.0200001,        "bearish"),
        (Decimal("0.03"),   "bullish"),
        (Decimal("-0.03"),  "bearish"),
        (0.5,               "bullish"),
        (-0.5,              "bearish"),
        (1.0,               "bullish"),
        (-1.0,              "bearish"),
    ])
    def test_parametrized(self, value, expected):
        assert label_from_return(value) == expected

    def test_zero_is_neutral(self):
        assert label_from_return(0.0) == "neutral"

    def test_exact_upper_threshold_is_neutral(self):
        assert label_from_return(0.02) == "neutral"

    def test_exact_lower_threshold_is_neutral(self):
        assert label_from_return(-0.02) == "neutral"

    def test_just_above_upper_threshold_is_bullish(self):
        assert label_from_return(0.020001) == "bullish"

    def test_just_below_lower_threshold_is_bearish(self):
        assert label_from_return(-0.020001) == "bearish"

    def test_decimal_bullish(self):
        assert label_from_return(Decimal("0.05")) == "bullish"

    def test_decimal_bearish(self):
        assert label_from_return(Decimal("-0.05")) == "bearish"

    def test_decimal_neutral(self):
        assert label_from_return(Decimal("0.01")) == "neutral"

    def test_large_positive_is_bullish(self):
        assert label_from_return(10.0) == "bullish"

    def test_large_negative_is_bearish(self):
        assert label_from_return(-10.0) == "bearish"

    def test_very_small_positive_is_neutral(self):
        assert label_from_return(0.001) == "neutral"

    def test_very_small_negative_is_neutral(self):
        assert label_from_return(-0.001) == "neutral"


# ===========================================================================
# UNIT: sort_by_website_order
# ===========================================================================

class TestSortByWebsiteOrder:

    def test_empty_list_returns_empty(self):
        assert sort_by_website_order([]) == []

    def test_single_item_unchanged(self):
        rows = [{"ticker": "AAPL"}]
        assert sort_by_website_order(rows) == rows

    def test_known_tickers_sorted_by_website_order(self):
        rows = [{"ticker": "AAPL"}, {"ticker": "KSS"}]
        result = sort_by_website_order(rows)
        assert result[0]["ticker"] == "KSS"
        assert result[1]["ticker"] == "AAPL"

    def test_unknown_tickers_sorted_after_known(self):
        rows = [{"ticker": "UNKNOWN"}, {"ticker": "AAPL"}]
        result = sort_by_website_order(rows)
        assert result[0]["ticker"] == "AAPL"
        assert result[1]["ticker"] == "UNKNOWN"

    def test_unknown_tickers_sorted_alphabetically_among_themselves(self):
        rows = [{"ticker": "ZZZ"}, {"ticker": "AAA"}, {"ticker": "AAPL"}]
        result = sort_by_website_order(rows)
        assert result[0]["ticker"] == "AAPL"
        assert result[1]["ticker"] == "AAA"
        assert result[2]["ticker"] == "ZZZ"

    def test_all_known_tickers_follow_website_order(self):
        sample = ["NVDA", "AAPL", "KSS", "DAL"]
        rows = [{"ticker": t} for t in sample]
        result = sort_by_website_order(rows)
        expected_order = sorted(sample, key=lambda t: TICKER_ORDER[t])
        assert [r["ticker"] for r in result] == expected_order

    def test_preserves_all_row_data(self):
        rows = [{"ticker": "AAPL", "value": 1}, {"ticker": "KSS", "value": 2}]
        result = sort_by_website_order(rows)
        assert result[0]["value"] == 2
        assert result[1]["value"] == 1

    def test_duplicate_tickers_preserved(self):
        rows = [{"ticker": "AAPL", "date": "2024-02"}, {"ticker": "AAPL", "date": "2024-01"}]
        result = sort_by_website_order(rows)
        assert len(result) == 2
        assert all(r["ticker"] == "AAPL" for r in result)


# ===========================================================================
# UNIT: label_from_return in aggregation scenarios
# ===========================================================================

class TestLabelAggregation:

    def _map_labels(self, rows: List[dict]) -> List[dict]:
        return [
            {
                "ticker": r["ticker"],
                "d30":  label_from_return(r.get("return_30d")),
                "d120": label_from_return(r.get("return_120d")),
                "d360": label_from_return(r.get("return_360d")),
            }
            for r in rows
        ]

    def test_all_bullish(self):
        rows = [{"ticker": "AAPL", "return_30d": 0.05, "return_120d": 0.10, "return_360d": 0.15}]
        result = self._map_labels(rows)
        assert result[0] == {"ticker": "AAPL", "d30": "bullish", "d120": "bullish", "d360": "bullish"}

    def test_all_bearish(self):
        rows = [{"ticker": "KSS", "return_30d": -0.05, "return_120d": -0.10, "return_360d": -0.15}]
        result = self._map_labels(rows)
        assert result[0] == {"ticker": "KSS", "d30": "bearish", "d120": "bearish", "d360": "bearish"}

    def test_mixed_labels(self):
        rows = [{"ticker": "DAL", "return_30d": 0.05, "return_120d": 0.0, "return_360d": -0.05}]
        result = self._map_labels(rows)
        assert result[0]["d30"] == "bullish"
        assert result[0]["d120"] == "neutral"
        assert result[0]["d360"] == "bearish"

    def test_null_returns_default_neutral(self):
        rows = [{"ticker": "BHP", "return_30d": None, "return_120d": None, "return_360d": None}]
        result = self._map_labels(rows)
        assert result[0] == {"ticker": "BHP", "d30": "neutral", "d120": "neutral", "d360": "neutral"}

    def test_multiple_rows_each_mapped_independently(self):
        rows = [
            {"ticker": "AAPL", "return_30d": 0.05,  "return_120d": 0.0, "return_360d": 0.0},
            {"ticker": "KSS",  "return_30d": -0.05, "return_120d": 0.0, "return_360d": 0.0},
        ]
        result = self._map_labels(rows)
        assert result[0]["d30"] == "bullish"
        assert result[1]["d30"] == "bearish"
