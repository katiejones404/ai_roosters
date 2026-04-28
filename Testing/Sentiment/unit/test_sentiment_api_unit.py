"""
test_sentiment_api_unit.py  -  UNIT TESTS
Tests for the sentiment API functions: label_from_return, get_sentiment_indicators,
and delete_ticker_indicators. Uses a fake in-memory DB session to avoid live DB calls.
"""
from __future__ import annotations

import math
from decimal import Decimal

import pytest

from app.api.sentiment import (
    delete_ticker_indicators,
    get_sentiment_indicators,
    label_from_return,
)
from Testing.Sentiment._fakes import FakeDB


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, "neutral"),
        ("not-a-number", "neutral"),
        (Decimal("0.03"), "bullish"),
        (Decimal("-0.03"), "bearish"),
        (0.0, "neutral"),
        (0.02, "neutral"),
        (-0.02, "neutral"),
        (0.0200001, "bullish"),
        (-0.0200001, "bearish"),
        (float("nan"), "neutral"),
        (float("inf"), "neutral"),
        (-float("inf"), "neutral"),
    ],
)
def test_label_from_return_edges(value, expected):
    assert label_from_return(value) == expected


def test_get_sentiment_indicators_empty_returns_empty_list():
    db = FakeDB()
    result = get_sentiment_indicators(ticker=None, db=db)
    assert result == []


def test_get_sentiment_indicators_maps_labels_and_close_price():
    db = FakeDB()
    db.seed_snapshots(
        [
            {
                "id": "1",
                "ticker": "RELIANCE.NS",
                "snapshot_date": "2022-02-28",
                "close_price": Decimal("123.45"),
                "return_30d": 0.05,
                "return_120d": -0.10,
                "return_360d": 0.0,
            }
        ]
    )

    result = get_sentiment_indicators(ticker=None, db=db)
    assert len(result) == 1
    row = result[0]
    assert row.ticker == "RELIANCE.NS"
    assert math.isclose(row.close_price, 123.45, rel_tol=0, abs_tol=1e-9)
    assert row.indicators.d30 == "bullish"
    assert row.indicators.d120 == "bearish"
    assert row.indicators.d360 == "neutral"


def test_get_sentiment_indicators_filters_by_ticker_param():
    db = FakeDB()
    db.seed_snapshots(
        [
            {
                "id": "1",
                "ticker": "RELIANCE.NS",
                "snapshot_date": "2022-02-28",
                "close_price": 100.0,
                "return_30d": 0.05,
                "return_120d": 0.0,
                "return_360d": 0.0,
            },
            {
                "id": "2",
                "ticker": "BP",
                "snapshot_date": "2022-02-28",
                "close_price": 200.0,
                "return_30d": -0.05,
                "return_120d": 0.0,
                "return_360d": 0.0,
            },
        ]
    )

    result = get_sentiment_indicators(ticker="reli", db=db)
    assert [r.ticker for r in result] == ["RELIANCE.NS"]


def test_delete_ticker_indicators_returns_deleted_count():
    db = FakeDB()
    db.seed_delete_rowcount(3)
    result = delete_ticker_indicators(ticker="BP", db=db)
    assert result == {"status": "ok", "deleted": 3}


def test_delete_ticker_indicators_zero_is_ok():
    db = FakeDB()
    db.seed_delete_rowcount(0)
    result = delete_ticker_indicators(ticker="MISSING", db=db)
    assert result == {"status": "ok", "deleted": 0}
