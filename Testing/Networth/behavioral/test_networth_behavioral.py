"""
test_networth_behavioral.py  ,  BEHAVIORAL TESTS
Behavioral / end-to-end API tests for the net worth tracking system.

Notes
-----
Tests run against an in-memory SQLite database via FastAPI TestClient.
Fixtures are defined in conftest.py for this folder.
Covers assets, liabilities, net worth summary, history snapshots,
authentication enforcement, and cross-user isolation.
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
# BEHAVIORAL: Authentication guard
# ===========================================================================

class TestNetworthAuthGuard:
    def test_summary_requires_auth(self, client):
        """GET /networth without token returns 401."""
        assert client.get(SUMMARY_URL).status_code == 401

    def test_assets_list_requires_auth(self, client):
        """GET /networth/assets without token returns 401."""
        assert client.get(ASSETS_URL).status_code == 401

    def test_add_asset_requires_auth(self, client):
        """POST /networth/assets without token returns 401."""
        assert client.post(ASSETS_URL, json=_ASSET).status_code == 401

    def test_liabilities_list_requires_auth(self, client):
        """GET /networth/liabilities without token returns 401."""
        assert client.get(LIABILITIES_URL).status_code == 401

    def test_add_liability_requires_auth(self, client):
        """POST /networth/liabilities without token returns 401."""
        assert client.post(LIABILITIES_URL, json=_LIABILITY).status_code == 401

    def test_history_requires_auth(self, client):
        """GET /networth/history without token returns 401."""
        assert client.get(HISTORY_URL).status_code == 401

    def test_snapshot_requires_auth(self, client):
        """POST /networth/snapshot without token returns 401."""
        assert client.post(SNAPSHOT_URL).status_code == 401


# ===========================================================================
# BEHAVIORAL: Summary , initial state
# ===========================================================================

class TestNetworthSummaryInitial:
    def test_empty_summary_returns_zeros(self, client, auth_headers):
        """A new user's net worth summary is all zeros with empty lists."""
        res = client.get(SUMMARY_URL, headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["total_assets"] == 0.0
        assert data["total_liabilities"] == 0.0
        assert data["net_worth"] == 0.0
        assert data["assets"] == []
        assert data["liabilities"] == []


# ===========================================================================
# BEHAVIORAL: Asset lifecycle
# ===========================================================================

class TestAssetLifecycle:
    def test_add_asset_returns_201(self, client, auth_headers):
        """Adding an asset returns 201 with the correct fields."""
        res = client.post(ASSETS_URL, headers=auth_headers, json=_ASSET)
        assert res.status_code == 201
        data = res.json()
        assert data["name"] == "Emergency Fund"
        assert data["category"] == "savings"
        assert data["balance"] == pytest.approx(5000.0)
        assert "id" in data

    def test_asset_appears_in_list(self, client, auth_headers):
        """The added asset appears when listing all assets."""
        res = client.get(ASSETS_URL, headers=auth_headers)
        assert res.status_code == 200
        names = [a["name"] for a in res.json()]
        assert "Emergency Fund" in names

    def test_asset_reflected_in_summary(self, client, auth_headers):
        """Adding an asset increases total_assets and net_worth in the summary."""
        res = client.get(SUMMARY_URL, headers=auth_headers)
        data = res.json()
        assert data["total_assets"] >= 5000.0
        assert data["net_worth"] == pytest.approx(
            data["total_assets"] - data["total_liabilities"]
        )

    def test_update_asset_balance(self, client, auth_headers):
        """PUT /networth/assets/{id} updates the asset balance."""
        asset_id = client.post(ASSETS_URL, headers=auth_headers, json={
            "name": "Car", "category": "vehicle", "balance": 15000.0,
        }).json()["id"]

        res = client.put(f"{ASSETS_URL}/{asset_id}", headers=auth_headers,
                         json={"balance": 12000.0})
        assert res.status_code == 200
        assert res.json()["balance"] == pytest.approx(12000.0)

    def test_update_asset_name(self, client, auth_headers):
        """PUT /networth/assets/{id} can update the asset name."""
        asset_id = client.post(ASSETS_URL, headers=auth_headers, json={
            "name": "Old Name", "category": "other", "balance": 100.0,
        }).json()["id"]

        res = client.put(f"{ASSETS_URL}/{asset_id}", headers=auth_headers,
                         json={"name": "New Name"})
        assert res.status_code == 200
        assert res.json()["name"] == "New Name"

    def test_delete_asset_returns_ok(self, client, auth_headers):
        """DELETE /networth/assets/{id} returns a success status."""
        asset_id = client.post(ASSETS_URL, headers=auth_headers, json={
            "name": "ToDelete", "category": "cash", "balance": 500.0,
        }).json()["id"]

        res = client.delete(f"{ASSETS_URL}/{asset_id}", headers=auth_headers)
        assert res.status_code == 200

    def test_delete_nonexistent_asset_returns_404(self, client, auth_headers):
        """Deleting an asset that doesn't exist returns 404."""
        res = client.delete(f"{ASSETS_URL}/00000000-fake-fake-fake-000000000000",
                            headers=auth_headers)
        assert res.status_code == 404

    def test_update_nonexistent_asset_returns_404(self, client, auth_headers):
        """Updating a non-existent asset returns 404."""
        res = client.put(f"{ASSETS_URL}/00000000-fake-fake-fake-000000000000",
                         headers=auth_headers, json={"balance": 999.0})
        assert res.status_code == 404


# ===========================================================================
# BEHAVIORAL: Liability lifecycle
# ===========================================================================

class TestLiabilityLifecycle:
    def test_add_liability_returns_201(self, client, auth_headers):
        """Adding a liability returns 201 with the correct fields."""
        res = client.post(LIABILITIES_URL, headers=auth_headers, json=_LIABILITY)
        assert res.status_code == 201
        data = res.json()
        assert data["name"] == "Student Loan"
        assert data["balance"] == pytest.approx(20000.0)
        assert "id" in data

    def test_liability_appears_in_list(self, client, auth_headers):
        """The added liability appears in GET /networth/liabilities."""
        res = client.get(LIABILITIES_URL, headers=auth_headers)
        names = [l["name"] for l in res.json()]
        assert "Student Loan" in names

    def test_liability_reflected_in_summary(self, client, auth_headers):
        """Adding a liability increases total_liabilities in the summary."""
        res = client.get(SUMMARY_URL, headers=auth_headers)
        assert res.json()["total_liabilities"] >= 20000.0

    def test_net_worth_formula_in_summary(self, client, auth_headers):
        """net_worth always equals total_assets - total_liabilities."""
        data = client.get(SUMMARY_URL, headers=auth_headers).json()
        assert data["net_worth"] == pytest.approx(
            data["total_assets"] - data["total_liabilities"], abs=0.01
        )

    def test_delete_liability_returns_ok(self, client, auth_headers):
        """DELETE /networth/liabilities/{id} removes the liability."""
        lid = client.post(LIABILITIES_URL, headers=auth_headers, json={
            "name": "ToDeleteLiab", "category": "credit_card", "balance": 1500.0,
        }).json()["id"]
        res = client.delete(f"{LIABILITIES_URL}/{lid}", headers=auth_headers)
        assert res.status_code == 200

    def test_delete_nonexistent_liability_returns_404(self, client, auth_headers):
        """Deleting a non-existent liability returns 404."""
        res = client.delete(f"{LIABILITIES_URL}/00000000-fake-fake-fake-000000000000",
                            headers=auth_headers)
        assert res.status_code == 404


# ===========================================================================
# BEHAVIORAL: History snapshots
# ===========================================================================

class TestNetworthHistory:
    def test_empty_history_returns_list(self, client, auth_headers):
        """GET /networth/history returns a list (may be empty initially)."""
        res = client.get(HISTORY_URL, headers=auth_headers)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_record_snapshot_returns_204(self, client, auth_headers):
        """POST /networth/snapshot stores a snapshot and returns 204."""
        res = client.post(SNAPSHOT_URL, headers=auth_headers)
        assert res.status_code == 204

    def test_snapshot_appears_in_history(self, client, auth_headers):
        """After recording a snapshot, it appears in GET /networth/history."""
        client.post(SNAPSHOT_URL, headers=auth_headers)
        res = client.get(HISTORY_URL, headers=auth_headers)
        assert len(res.json()) >= 1

    def test_history_days_param_accepted(self, client, auth_headers):
        """GET /networth/history?days=7 returns a 200 response."""
        res = client.get(f"{HISTORY_URL}?days=7", headers=auth_headers)
        assert res.status_code == 200

    def test_history_days_param_out_of_range_rejected(self, client, auth_headers):
        """days=0 is rejected (minimum is 1)."""
        res = client.get(f"{HISTORY_URL}?days=0", headers=auth_headers)
        assert res.status_code == 422


# ===========================================================================
# BEHAVIORAL: Cross-user isolation
# ===========================================================================

class TestNetworthIsolation:
    def test_users_cannot_see_each_others_assets(
        self, client, auth_headers, other_headers
    ):
        """Each user's assets are private."""
        client.post(ASSETS_URL, headers=auth_headers, json={
            "name": "UserA_Asset", "category": "cash", "balance": 100.0,
        })
        client.post(ASSETS_URL, headers=other_headers, json={
            "name": "UserB_Asset", "category": "cash", "balance": 200.0,
        })

        user_a = {a["name"] for a in client.get(ASSETS_URL, headers=auth_headers).json()}
        user_b = {a["name"] for a in client.get(ASSETS_URL, headers=other_headers).json()}

        assert "UserA_Asset" in user_a
        assert "UserB_Asset" not in user_a
        assert "UserB_Asset" in user_b
        assert "UserA_Asset" not in user_b

    def test_user_cannot_delete_other_users_asset(
        self, client, auth_headers, other_headers
    ):
        """User B cannot delete User A's asset."""
        asset_id = client.post(ASSETS_URL, headers=auth_headers, json={
            "name": "Protected", "category": "other", "balance": 50.0,
        }).json()["id"]

        res = client.delete(f"{ASSETS_URL}/{asset_id}", headers=other_headers)
        assert res.status_code == 404
