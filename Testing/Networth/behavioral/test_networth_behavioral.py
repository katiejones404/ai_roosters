"""
test_networth_behavioral.py  -  EXPANDED BEHAVIORAL TESTS

End-to-end API tests using FastAPI TestClient + in-memory DB.

Covers:
- Auth enforcement
- Asset & liability lifecycle
- Summary correctness
- Snapshot/history behavior
- Cross-user isolation
- Validation & edge cases
"""

from __future__ import annotations

import pytest

ASSETS_URL = "/api/networth/assets"
LIABILITIES_URL = "/api/networth/liabilities"
SUMMARY_URL = "/api/networth"
HISTORY_URL = "/api/networth/history"
SNAPSHOT_URL = "/api/networth/snapshot"

_ASSET = {"name": "Emergency Fund", "category": "savings", "balance": 5000.0}
_LIABILITY = {"name": "Student Loan", "category": "student_loan", "balance": 20000.0}


# ===========================================================================
# AUTH GUARD
# ===========================================================================

class TestNetworthAuthGuard:
    def test_all_endpoints_require_auth(self, client):
        assert client.get(SUMMARY_URL).status_code == 401
        assert client.get(ASSETS_URL).status_code == 401
        assert client.post(ASSETS_URL, json=_ASSET).status_code == 401
        assert client.get(LIABILITIES_URL).status_code == 401
        assert client.post(LIABILITIES_URL, json=_LIABILITY).status_code == 401
        assert client.get(HISTORY_URL).status_code == 401
        assert client.post(SNAPSHOT_URL).status_code == 401


# ===========================================================================
# SUMMARY INITIAL STATE
# ===========================================================================

class TestNetworthSummaryInitial:
    def test_empty_summary(self, client, auth_headers):
        res = client.get(SUMMARY_URL, headers=auth_headers)
        data = res.json()

        assert res.status_code == 200
        assert data["total_assets"] == 0.0
        assert data["total_liabilities"] == 0.0
        assert data["net_worth"] == 0.0
        assert data["assets"] == []
        assert data["liabilities"] == []


# ===========================================================================
# ASSET LIFECYCLE
# ===========================================================================

class TestAssetLifecycle:

    def test_add_asset(self, client, auth_headers):
        res = client.post(ASSETS_URL, headers=auth_headers, json=_ASSET)
        assert res.status_code == 201
        assert res.json()["name"] == _ASSET["name"]

    def test_asset_list_contains_added(self, client, auth_headers):
        client.post(ASSETS_URL, headers=auth_headers, json=_ASSET)
        res = client.get(ASSETS_URL, headers=auth_headers)

        assert any(a["name"] == _ASSET["name"] for a in res.json())

    def test_update_asset_balance(self, client, auth_headers):
        asset = client.post(ASSETS_URL, headers=auth_headers, json=_ASSET).json()

        res = client.put(
            f"{ASSETS_URL}/{asset['id']}",
            headers=auth_headers,
            json={"balance": 9999.0},
        )

        assert res.status_code == 200
        assert res.json()["balance"] == pytest.approx(9999.0)

    def test_partial_update_preserves_fields(self, client, auth_headers):
        asset = client.post(ASSETS_URL, headers=auth_headers, json=_ASSET).json()

        res = client.put(
            f"{ASSETS_URL}/{asset['id']}",
            headers=auth_headers,
            json={"balance": 123.0},
        )

        data = res.json()
        assert data["balance"] == 123.0
        assert data["name"] == _ASSET["name"]

    def test_delete_asset(self, client, auth_headers):
        asset_id = client.post(ASSETS_URL, headers=auth_headers, json=_ASSET).json()["id"]

        res = client.delete(f"{ASSETS_URL}/{asset_id}", headers=auth_headers)
        assert res.status_code == 200

    def test_delete_asset_idempotency(self, client, auth_headers):
        asset_id = client.post(ASSETS_URL, headers=auth_headers, json=_ASSET).json()["id"]

        assert client.delete(f"{ASSETS_URL}/{asset_id}", headers=auth_headers).status_code == 200
        assert client.delete(f"{ASSETS_URL}/{asset_id}", headers=auth_headers).status_code == 404

    def test_update_nonexistent_asset(self, client, auth_headers):
        res = client.put(
            f"{ASSETS_URL}/fake-id",
            headers=auth_headers,
            json={"balance": 100},
        )
        assert res.status_code == 404


# ===========================================================================
# LIABILITY LIFECYCLE
# ===========================================================================

class TestLiabilityLifecycle:

    def test_add_liability(self, client, auth_headers):
        res = client.post(LIABILITIES_URL, headers=auth_headers, json=_LIABILITY)
        assert res.status_code == 201

    def test_liability_list_contains_added(self, client, auth_headers):
        client.post(LIABILITIES_URL, headers=auth_headers, json=_LIABILITY)
        res = client.get(LIABILITIES_URL, headers=auth_headers)

        assert any(l["name"] == _LIABILITY["name"] for l in res.json())

    def test_delete_liability(self, client, auth_headers):
        lid = client.post(LIABILITIES_URL, headers=auth_headers, json=_LIABILITY).json()["id"]

        res = client.delete(f"{LIABILITIES_URL}/{lid}", headers=auth_headers)
        assert res.status_code == 200

    def test_delete_nonexistent_liability(self, client, auth_headers):
        res = client.delete(f"{LIABILITIES_URL}/fake-id", headers=auth_headers)
        assert res.status_code == 404


# ===========================================================================
# SUMMARY CONSISTENCY
# ===========================================================================

class TestSummaryConsistency:

    def test_networth_formula(self, client, auth_headers):
        client.post(ASSETS_URL, headers=auth_headers, json=_ASSET)
        client.post(LIABILITIES_URL, headers=auth_headers, json=_LIABILITY)

        data = client.get(SUMMARY_URL, headers=auth_headers).json()

        assert data["net_worth"] == pytest.approx(
            data["total_assets"] - data["total_liabilities"]
        )

    def test_summary_updates_after_delete(self, client, auth_headers):
        asset_id = client.post(ASSETS_URL, headers=auth_headers, json=_ASSET).json()["id"]

        before = client.get(SUMMARY_URL, headers=auth_headers).json()

        client.delete(f"{ASSETS_URL}/{asset_id}", headers=auth_headers)

        after = client.get(SUMMARY_URL, headers=auth_headers).json()

        assert after["total_assets"] <= before["total_assets"]


# ===========================================================================
# HISTORY / SNAPSHOTS
# ===========================================================================

class TestNetworthHistory:

    def test_snapshot_and_history(self, client, auth_headers):
        client.post(SNAPSHOT_URL, headers=auth_headers)
        res = client.get(HISTORY_URL, headers=auth_headers)

        assert res.status_code == 200
        assert isinstance(res.json(), list)
        assert len(res.json()) >= 1

    def test_history_sorted(self, client, auth_headers):
        client.post(SNAPSHOT_URL, headers=auth_headers)
        client.post(SNAPSHOT_URL, headers=auth_headers)

        data = client.get(HISTORY_URL, headers=auth_headers).json()

        if len(data) >= 2:
            assert data[0]["snapshot_date"] >= data[1]["snapshot_date"]

    def test_history_days_param(self, client, auth_headers):
        assert client.get(f"{HISTORY_URL}?days=7", headers=auth_headers).status_code == 200
        assert client.get(f"{HISTORY_URL}?days=0", headers=auth_headers).status_code == 422


# ===========================================================================
# VALIDATION
# ===========================================================================

class TestValidation:

    def test_missing_fields_asset(self, client, auth_headers):
        res = client.post(ASSETS_URL, headers=auth_headers, json={"balance": 100})
        assert res.status_code == 422

    def test_invalid_balance(self, client, auth_headers):
        res = client.post(ASSETS_URL, headers=auth_headers, json={
            "name": "Bad", "category": "cash", "balance": "abc"
        })
        assert res.status_code == 422


# ===========================================================================
# CROSS USER ISOLATION
# ===========================================================================

class TestNetworthIsolation:

    def test_users_isolated(self, client, auth_headers, other_headers):
        client.post(ASSETS_URL, headers=auth_headers, json={
            "name": "A", "category": "cash", "balance": 100
        })
        client.post(ASSETS_URL, headers=other_headers, json={
            "name": "B", "category": "cash", "balance": 200
        })

        a = {x["name"] for x in client.get(ASSETS_URL, headers=auth_headers).json()}
        b = {x["name"] for x in client.get(ASSETS_URL, headers=other_headers).json()}

        assert "A" in a and "B" not in a
        assert "B" in b and "A" not in b

    def test_user_cannot_delete_other_users_asset(self, client, auth_headers, other_headers):
        asset_id = client.post(ASSETS_URL, headers=auth_headers, json={
            "name": "Protected", "category": "other", "balance": 50.0,
        }).json()["id"]

        res = client.delete(f"{ASSETS_URL}/{asset_id}", headers=other_headers)

        # Correct behavior: hidden resource → 404
        assert res.status_code == 404