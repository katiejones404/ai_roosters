"""
test_networth_unit.py  -  UNIT TESTS
Unit tests for the net worth service helper functions and calculation logic.

Notes
-----
All DB calls are mocked - no live database is required.
Tests cover: safe_float, safe_datetime_to_str, row_to_dict,
net worth arithmetic, and the CRUD service layer.
"""

from __future__ import annotations

import math
import os
import sys
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, call
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

from app.services.networth import (  # noqa: E402
    safe_float,
    safe_datetime_to_str,
    row_to_dict,
)
from app.schema.schemas import (  # noqa: E402
    NetworthAssetCreate,
    NetworthAssetUpdate,
    NetworthLiabilityCreate,
    NetworthLiabilityUpdate,
)


# ===========================================================================
# UNIT: safe_float
# ===========================================================================

class TestSafeFloat:
    @pytest.mark.parametrize("value,default,expected", [
        (None, 0.0, None),           # None + default=0 = None (optional field)
        (None, 1.0, 1.0),            # None + non-zero default = default
        ("42.5", 0.0, 42.5),         # numeric string
        (Decimal("1234.56"), 0.0, 1234.56),
        (float("nan"), 0.0, 0.0),    # NaN = default
        (float("inf"), 0.0, 0.0),    # Inf = default
        (-float("inf"), 5.0, 5.0),   # -Inf = non-zero default
        ("bad", 0.0, 0.0),           # invalid string = default
        (0, 0.0, 0.0),
        (-100.0, 0.0, -100.0),       # negative
    ])
    def test_safe_float_parametrized(self, value, default, expected):
        result = safe_float(value, default)
        if expected is None:
            assert result is None
        else:
            assert result == pytest.approx(expected)


# ===========================================================================
# UNIT: safe_datetime_to_str
# ===========================================================================

class TestSafeDatetimeToStr:
    def test_none_returns_none(self):
        assert safe_datetime_to_str(None) is None

    def test_string_passthrough(self):
        s = "2026-01-01T00:00:00"
        assert safe_datetime_to_str(s) == s

    def test_datetime_returns_isoformat(self):
        dt = datetime(2026, 3, 15, 9, 0, 0)
        result = safe_datetime_to_str(dt)
        assert "2026-03-15" in result

    def test_other_type_stringified(self):
        assert safe_datetime_to_str(999) == "999"


# ===========================================================================
# UNIT: row_to_dict
# ===========================================================================

class TestRowToDict:
    def test_none_returns_none(self):
        assert row_to_dict(None) is None

    def test_dict_passthrough(self):
        d = {"name": "Savings", "balance": 1000.0}
        assert row_to_dict(d) == d

    def test_row_with_mapping(self):
        mock_row = MagicMock()
        mock_row._mapping = {"id": "abc", "name": "Car"}
        assert row_to_dict(mock_row) == {"id": "abc", "name": "Car"}


# ===========================================================================
# UNIT: Net worth arithmetic
# ===========================================================================

class TestNetworthArithmetic:
    """
    Net worth = total_assets - total_liabilities
    total_assets = portfolio_value + manual_asset_balances
    """

    @pytest.mark.parametrize(
        "portfolio_value,asset_balances,liability_balances,expected_nw",
        [
            (0.0, [], [], 0.0),
            (5000.0, [1000.0, 2000.0], [500.0], 7500.0),
            (0.0, [10000.0], [15000.0], -5000.0),  # liabilities exceed assets
            (1000.0, [], [], 1000.0),               # portfolio only
            (0.0, [5000.0], [], 5000.0),            # asset only
        ],
    )
    def test_net_worth_calculation(
        self, portfolio_value, asset_balances, liability_balances, expected_nw
    ):
        total_manual = sum(asset_balances)
        total_assets = portfolio_value + total_manual
        total_liabilities = sum(liability_balances)
        net_worth = total_assets - total_liabilities
        assert net_worth == pytest.approx(expected_nw)

    def test_net_worth_with_fractional_values(self):
        portfolio = 1234.56
        assets = [100.01, 200.02]
        liabilities = [50.50]
        expected = portfolio + sum(assets) - sum(liabilities)
        assert expected == pytest.approx(1484.09, rel=1e-4)

    def test_zero_net_worth_when_balanced(self):
        portfolio = 1000.0
        assets = [500.0]
        liabilities = [1500.0]
        nw = (portfolio + sum(assets)) - sum(liabilities)
        assert nw == pytest.approx(0.0)


# ===========================================================================
# UNIT: Asset CRUD service (mocked DB)
# ===========================================================================

class TestAddAsset:
    def test_add_asset_returns_correct_schema(self):
        """add_asset returns a NetworthAssetOut with the supplied values."""
        from app.services.networth import add_asset

        db = MagicMock()
        uid = uuid4()
        item = NetworthAssetCreate(name="Emergency Fund", category="savings", balance=5000.0)

        result = add_asset(db, uid, item)

        assert result.name == "Emergency Fund"
        assert result.category == "savings"
        assert result.balance == pytest.approx(5000.0)
        assert result.id  # UUID string was generated
        db.execute.assert_called_once()
        db.commit.assert_called_once()

    def test_add_asset_id_is_unique_each_call(self):
        """Each call to add_asset generates a distinct UUID."""
        from app.services.networth import add_asset

        uid = uuid4()
        item = NetworthAssetCreate(name="House", category="real_estate", balance=250000.0)

        db1, db2 = MagicMock(), MagicMock()
        r1 = add_asset(db1, uid, item)
        r2 = add_asset(db2, uid, item)
        assert r1.id != r2.id


class TestDeleteAsset:
    def test_delete_returns_true_when_found(self):
        """delete_asset returns True when a row is deleted."""
        from app.services.networth import delete_asset

        db = MagicMock()
        db.execute.return_value.rowcount = 1
        assert delete_asset(db, uuid4(), "some-asset-id") is True
        db.commit.assert_called_once()

    def test_delete_returns_false_when_not_found(self):
        """delete_asset returns False when no row matches."""
        from app.services.networth import delete_asset

        db = MagicMock()
        db.execute.return_value.rowcount = 0
        assert delete_asset(db, uuid4(), "missing-id") is False


# ===========================================================================
# UNIT: Liability CRUD service (mocked DB)
# ===========================================================================

class TestAddLiability:
    def test_add_liability_returns_correct_schema(self):
        """add_liability returns a NetworthLiabilityOut with the supplied values."""
        from app.services.networth import add_liability

        db = MagicMock()
        uid = uuid4()
        item = NetworthLiabilityCreate(name="Student Loan", category="student_loan",
                                       balance=30000.0)

        result = add_liability(db, uid, item)

        assert result.name == "Student Loan"
        assert result.category == "student_loan"
        assert result.balance == pytest.approx(30000.0)
        assert result.id
        db.commit.assert_called_once()


class TestDeleteLiability:
    def test_delete_returns_true_when_found(self):
        from app.services.networth import delete_liability

        db = MagicMock()
        db.execute.return_value.rowcount = 1
        assert delete_liability(db, uuid4(), "some-liability-id") is True

    def test_delete_returns_false_when_not_found(self):
        from app.services.networth import delete_liability

        db = MagicMock()
        db.execute.return_value.rowcount = 0
        assert delete_liability(db, uuid4(), "missing-id") is False


# ===========================================
# UNIT: update_asset - field selection

class TestUpdateAsset:
    def _make_db_with_row(self, name, category, balance):
        """Return a mock db whose fetchone returns a row with the given values."""
        db = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        db.execute.return_value = mock_result
        # Second execute (SELECT after UPDATE) returns a row
        mock_row = MagicMock()
        mock_row._mapping = {
            "id": "test-id", "name": name,
            "category": category, "balance": balance, "updated_at": None,
        }
        db.execute.return_value.fetchone.return_value = mock_row
        return db

    def test_no_fields_returns_none(self):
        """If the update payload has no fields set, update_asset returns None."""
        from app.services.networth import update_asset

        db = MagicMock()
        item = NetworthAssetUpdate()  # all None
        result = update_asset(db, uuid4(), "some-id", item)
        assert result is None
        db.execute.assert_not_called()

    def test_update_balance_only(self):
        """Updating only balance generates a SQL statement with that field."""
        from app.services.networth import update_asset

        db = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        db.execute.return_value = mock_result
        mock_row = MagicMock()
        mock_row._mapping = {
            "id": "x", "name": "Savings", "category": "savings",
            "balance": 6000.0, "updated_at": None,
        }
        db.execute.return_value.fetchone.return_value = mock_row

        item = NetworthAssetUpdate(balance=6000.0)
        result = update_asset(db, uuid4(), "x", item)
        assert result is not None
        # Verify that the UPDATE was called with balance param
        first_call_sql = str(db.execute.call_args_list[0][0][0])
        assert "balance" in first_call_sql.lower() or "bal" in str(
            db.execute.call_args_list[0][0][1]
        )
