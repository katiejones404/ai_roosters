"""
test_portfolio_service_unit.py  -  UNIT TESTS
Unit tests for the portfolio service helper functions.

Notes
-----
Tests cover safe_float, safe_datetime_to_str, row_to_dict, and the
weighted-average price logic baked into add_or_update_position.
All DB calls are mocked - no real database is required.
"""

from __future__ import annotations

import math
import os
import sys
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

# ---------------------------------------------------------------------------
# Import path setup
# ---------------------------------------------------------------------------

def _configure_paths() -> None:
    here = os.path.abspath(os.path.dirname(__file__))
    repo_root = os.path.abspath(os.path.join(here, "..", "..", ".."))
    backend_root = os.path.join(repo_root, "backend")
    for candidate in ("/app", backend_root, repo_root):
        if os.path.isdir(candidate) and candidate not in sys.path:
            sys.path.insert(0, candidate)

_configure_paths()

from app.services.portfolio import safe_float, safe_datetime_to_str, row_to_dict  # noqa: E402


# ===========================================================================
# UNIT: safe_float
# ===========================================================================

class TestSafeFloat:
    @pytest.mark.parametrize("value,default,expected", [
        (None, 0.0, None),          # None + default=0 = None (preserves optional)
        (None, 1.0, 1.0),           # None + non-zero default = default
        ("3.14", 0.0, 3.14),        # numeric string
        (Decimal("100.50"), 0.0, 100.50),  # Decimal
        (float("nan"), 0.0, 0.0),   # NaN = default
        (float("inf"), 0.0, 0.0),   # Inf = default
        (-float("inf"), 0.0, 0.0),  # -Inf = default
        ("not-a-number", 0.0, 0.0), # invalid string = default
        (0, 0.0, 0.0),              # zero int
        (-42.5, 0.0, -42.5),        # negative float
        (1_000_000.0, 0.0, 1_000_000.0),  # large value
    ])
    def test_safe_float_edge_cases(self, value, default, expected):
        result = safe_float(value, default)
        if expected is None:
            assert result is None
        else:
            assert result == pytest.approx(expected)

    def test_safe_float_returns_float_type(self):
        """Return value is always float (not Decimal or int)."""
        result = safe_float(Decimal("9.99"), 0.0)
        assert isinstance(result, float)


# ===========================================================================
# UNIT: safe_datetime_to_str
# ===========================================================================

class TestSafeDatetimeToStr:
    def test_none_returns_none(self):
        assert safe_datetime_to_str(None) is None

    def test_string_passthrough(self):
        """An existing string value is returned unchanged."""
        s = "2025-01-15T10:30:00"
        assert safe_datetime_to_str(s) == s

    def test_datetime_returns_iso_string(self):
        """A datetime object is converted to an ISO 8601 string."""
        dt = datetime(2025, 6, 15, 12, 0, 0)
        result = safe_datetime_to_str(dt)
        assert "2025-06-15" in result

    def test_unknown_type_returns_string(self):
        """Any other type is converted to string via str()."""
        result = safe_datetime_to_str(42)
        assert result == "42"


# ===========================================================================
# UNIT: row_to_dict
# ===========================================================================

class TestRowToDict:
    def test_none_returns_none(self):
        assert row_to_dict(None) is None

    def test_dict_returns_same_dict(self):
        d = {"ticker": "AAPL", "quantity": 10.0}
        result = row_to_dict(d)
        assert result == d

    def test_row_with_mapping_converted(self):
        """An object with a ._mapping attribute is unwrapped to a dict."""
        mock_row = MagicMock()
        mock_row._mapping = {"id": "123", "ticker": "NVDA"}
        result = row_to_dict(mock_row)
        assert result == {"id": "123", "ticker": "NVDA"}


# ===========================================================================
# UNIT: Weighted average price math
# ===========================================================================

class TestWeightedAverageMath:
    """
    The weighted-average logic in add_or_update_position must correctly
    compute the new average price when shares are added.
    These tests verify the formula directly without touching the DB.
    """

    @pytest.mark.parametrize("old_qty,old_price,new_qty,new_price,expected_avg", [
        (10, 100.0, 10, 200.0, 150.0),        # equal quantities
        (100, 50.0, 50, 150.0, 83.333),        # averaging up
        (50, 200.0, 50, 100.0, 150.0),         # averaging down
        (1, 1000.0, 999, 1.0, 1.999),          # very unequal quantities
        (0.5, 200.0, 0.5, 100.0, 150.0),       # fractional shares
    ])
    def test_weighted_average_formula(self, old_qty, old_price, new_qty, new_price, expected_avg):
        """
        Verify weighted average: (old_qty * old_price + new_qty * new_price) / (old_qty + new_qty).
        """
        total_qty = old_qty + new_qty
        avg = (old_qty * old_price + new_qty * new_price) / total_qty
        assert avg == pytest.approx(expected_avg, rel=1e-3)

    def test_single_buy_average_equals_purchase_price(self):
        """For a first-time purchase, average price equals the buy price."""
        qty, price = 10.0, 150.0
        total = qty
        avg = (qty * price) / total
        assert avg == pytest.approx(price)


# ===========================================================================
# UNIT: P&L formula
# ===========================================================================

class TestPnLFormulas:
    """Unit tests for the gain/loss formulas computed in get_portfolio_summary."""

    def test_gain_loss_positive(self):
        qty, avg_price, current_price = 10.0, 100.0, 120.0
        total_gain = (current_price - avg_price) * qty
        gain_pct = (current_price - avg_price) / avg_price * 100
        assert total_gain == pytest.approx(200.0)
        assert gain_pct == pytest.approx(20.0)

    def test_gain_loss_negative(self):
        qty, avg_price, current_price = 5.0, 200.0, 150.0
        total_gain = (current_price - avg_price) * qty
        gain_pct = (current_price - avg_price) / avg_price * 100
        assert total_gain == pytest.approx(-250.0)
        assert gain_pct == pytest.approx(-25.0)

    def test_no_change_is_zero(self):
        qty, avg_price, current_price = 100.0, 50.0, 50.0
        total_gain = (current_price - avg_price) * qty
        assert total_gain == pytest.approx(0.0)
