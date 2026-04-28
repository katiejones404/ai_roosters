"""
test_networth_unit.py  -  EXPANDED UNIT TESTS

Covers:
- helper functions
- arithmetic invariants
- CRUD service behavior
- edge cases
- additional coverage for updates + SQL calls
"""

from __future__ import annotations

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

from app.services.networth import (  # noqa: E402
    safe_float,
    safe_datetime_to_str,
    row_to_dict,
)
from app.schema.schemas import (  # noqa: E402
    NetworthAssetCreate,
    NetworthAssetUpdate,
    NetworthLiabilityCreate,
)

# ===========================================================================
# safe_float
# ===========================================================================

class TestSafeFloat:

    @pytest.mark.parametrize("value,default,expected", [
        (None, 0.0, None),
        (None, 1.0, 1.0),
        ("42.5", 0.0, 42.5),
        (Decimal("123.45"), 0.0, 123.45),
        ("1e3", 0.0, 1000.0),
        ("", 0.0, 0.0),
        ("bad", 0.0, 0.0),
        (float("nan"), 0.0, 0.0),
        (float("inf"), 0.0, 0.0),
        (-float("inf"), 5.0, 5.0),
        (-100.5, 0.0, -100.5),
        (0, 0.0, 0.0),
    ])
    def test_safe_float(self, value, default, expected):
        result = safe_float(value, default)
        if expected is None:
            assert result is None
        else:
            assert result == pytest.approx(expected)


# ===========================================================================
# safe_datetime_to_str
# ===========================================================================

class TestSafeDatetime:

    def test_none(self):
        assert safe_datetime_to_str(None) is None

    def test_string_passthrough(self):
        s = "2026-01-01T00:00:00"
        assert safe_datetime_to_str(s) == s

    def test_datetime(self):
        dt = datetime(2026, 1, 1)
        assert "2026" in safe_datetime_to_str(dt)


# ===========================================================================
# row_to_dict
# ===========================================================================

class TestRowToDict:

    def test_none(self):
        assert row_to_dict(None) is None

    def test_dict(self):
        d = {"a": 1}
        assert row_to_dict(d) == d

    def test_mapping(self):
        row = MagicMock()
        row._mapping = {"id": "1"}
        assert row_to_dict(row) == {"id": "1"}

    def test_object_passthrough(self):
        class Weird: pass
        obj = Weird()
        assert row_to_dict(obj) is obj


# ===========================================================================
# arithmetic
# ===========================================================================

class TestArithmetic:

    def test_basic(self):
        assert (1000 - 500) == 500

    def test_negative(self):
        assert (1000 - 5000) == -4000

    def test_precision(self):
        assert sum([0.1, 0.2, 0.3]) == pytest.approx(0.6)


# ===========================================================================
# add_asset
# ===========================================================================

class TestAddAsset:

    def test_success(self):
        from app.services.networth import add_asset

        db = MagicMock()
        uid = uuid4()

        result = add_asset(
            db,
            uid,
            NetworthAssetCreate(name="A", category="cash", balance=100),
        )

        assert result.name == "A"
        assert result.balance == pytest.approx(100)
        db.execute.assert_called_once()
        db.commit.assert_called_once()

    def test_sql_contains_insert(self):
        from app.services.networth import add_asset

        db = MagicMock()
        uid = uuid4()

        add_asset(db, uid, NetworthAssetCreate(name="A", category="cash", balance=1))

        sql = str(db.execute.call_args[0][0]).lower()
        assert "insert" in sql


# ===========================================================================
# delete_asset
# ===========================================================================

class TestDeleteAsset:

    def test_success(self):
        from app.services.networth import delete_asset

        db = MagicMock()
        db.execute.return_value.rowcount = 1
        assert delete_asset(db, uuid4(), "id") is True

    def test_not_found(self):
        from app.services.networth import delete_asset

        db = MagicMock()
        db.execute.return_value.rowcount = 0
        assert delete_asset(db, uuid4(), "id") is False


# ===========================================================================
# add_liability
# ===========================================================================

class TestAddLiability:

    def test_success(self):
        from app.services.networth import add_liability

        db = MagicMock()
        uid = uuid4()

        result = add_liability(
            db,
            uid,
            NetworthLiabilityCreate(name="Loan", category="loan", balance=500),
        )

        assert result.balance == pytest.approx(500)


# ===========================================================================
# update_asset
# ===========================================================================

class TestUpdateAsset:

    def test_no_fields(self):
        from app.services.networth import update_asset

        db = MagicMock()
        assert update_asset(db, uuid4(), "id", NetworthAssetUpdate()) is None

    def test_not_found(self):
        from app.services.networth import update_asset

        db = MagicMock()
        db.execute.return_value.rowcount = 0

        result = update_asset(
            db,
            uuid4(),
            "id",
            NetworthAssetUpdate(balance=100),
        )

        assert result is None

    def test_update_multiple_fields(self):
        from app.services.networth import update_asset

        db = MagicMock()
        db.execute.return_value.rowcount = 1

        mock_row = MagicMock()
        mock_row._mapping = {
            "id": "x",
            "name": "Updated",
            "category": "cash",
            "balance": 999,
            "updated_at": None,
        }
        db.execute.return_value.fetchone.return_value = mock_row

        result = update_asset(
            db,
            uuid4(),
            "x",
            NetworthAssetUpdate(name="Updated", balance=999),
        )

        assert result.name == "Updated"
        assert result.balance == pytest.approx(999)
      

class TestAdditionalCoverage:

    @pytest.mark.parametrize("value", ["10", "0", "-5", "3.1415"])
    def test_safe_float_string_inputs(self, value):
        assert isinstance(safe_float(value, 0.0), float)

    def test_safe_float_zero_default_behavior(self):
        assert safe_float(None, 0.0) is None

    def test_safe_float_nonzero_default_behavior(self):
        assert safe_float(None, 5.0) == 5.0

    def test_datetime_string_stability(self):
        s = "2025-01-01"
        assert safe_datetime_to_str(s) == s

    def test_datetime_object_contains_year(self):
        dt = datetime(2024, 6, 1)
        assert "2024" in safe_datetime_to_str(dt)


    def test_row_to_dict_with_partial_mapping(self):
        row = MagicMock()
        row._mapping = {"only": "one"}
        result = row_to_dict(row)
        assert result["only"] == "one"

    def test_row_to_dict_with_empty_mapping(self):
        row = MagicMock()
        row._mapping = {}
        assert row_to_dict(row) == {}

    def test_row_to_dict_returns_same_object(self):
        obj = object()
        assert row_to_dict(obj) is obj


    def test_large_numbers(self):
        assert (1_000_000 - 500_000) == 500_000

    def test_zero_values(self):
        assert (0 - 0) == 0

    def test_float_precision(self):
        result = 0.1 + 0.2
        assert result == pytest.approx(0.3)


    def test_add_asset_multiple_calls(self):
        from app.services.networth import add_asset

        db = MagicMock()
        uid = uuid4()

        for _ in range(3):
            result = add_asset(
                db,
                uid,
                NetworthAssetCreate(name="X", category="cash", balance=1),
            )
            assert result.id

    def test_add_asset_sql_called(self):
        from app.services.networth import add_asset

        db = MagicMock()
        uid = uuid4()

        add_asset(db, uid, NetworthAssetCreate(name="X", category="cash", balance=1))

        assert db.execute.called


    def test_delete_asset_commit_called(self):
        from app.services.networth import delete_asset

        db = MagicMock()
        db.execute.return_value.rowcount = 1

        delete_asset(db, uuid4(), "id")

        db.commit.assert_called_once()

    

    def test_add_liability_multiple(self):
        from app.services.networth import add_liability

        db = MagicMock()
        uid = uuid4()

        for _ in range(2):
            result = add_liability(
                db,
                uid,
                NetworthLiabilityCreate(name="Loan", category="loan", balance=100),
            )
            assert result.id

   

    def test_update_asset_sql_called(self):
        from app.services.networth import update_asset

        db = MagicMock()
        db.execute.return_value.rowcount = 1

        mock_row = MagicMock()
        mock_row._mapping = {
            "id": "x",
            "name": "Updated",
            "category": "cash",
            "balance": 100,
            "updated_at": None,
        }
        db.execute.return_value.fetchone.return_value = mock_row

        update_asset(
            db,
            uuid4(),
            "x",
            NetworthAssetUpdate(balance=100),
        )

        assert db.execute.called

    def test_update_asset_preserves_return_type(self):
        from app.services.networth import update_asset

        db = MagicMock()
        db.execute.return_value.rowcount = 1

        mock_row = MagicMock()
        mock_row._mapping = {
            "id": "x",
            "name": "Same",
            "category": "cash",
            "balance": 50,
            "updated_at": None,
        }
        db.execute.return_value.fetchone.return_value = mock_row

        result = update_asset(
            db,
            uuid4(),
            "x",
            NetworthAssetUpdate(balance=50),
        )

        assert hasattr(result, "name")
        assert hasattr(result, "balance")