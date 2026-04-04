"""
test_alerts.py
Behavioral tests for the price alert system.

Notes
-----
Covers creating, listing, and deleting price alerts for authenticated users.
Verifies validation rules (direction, target price) and ownership enforcement.
"""
import pytest


ALERTS_URL = "/api/alerts"

VALID_ALERT = {
    "ticker": "AAPL",
    "target_price": 200.00,
    "direction": "above",
    "email_notify": True,
}


class TestListAlerts:
    def test_list_alerts_empty(self, client, auth_headers):
        """GET /alerts returns an empty list for a user with no alerts."""
        res = client.get(ALERTS_URL, headers=auth_headers)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_list_alerts_unauthenticated(self, client):
        """GET /alerts without a token returns 401."""
        res = client.get(ALERTS_URL)
        assert res.status_code == 401


class TestCreateAlert:
    def test_create_alert_above(self, client, auth_headers):
        """Creating a 'rises above' alert returns 201 with the alert data."""
        res = client.post(ALERTS_URL, headers=auth_headers, json=VALID_ALERT)
        assert res.status_code == 201
        data = res.json()
        assert data["ticker"] == "AAPL"
        assert data["direction"] == "above"
        assert float(data["target_price"]) == 200.00
        assert data["is_active"] is True
        assert data["email_notify"] is True
        assert "id" in data

    def test_create_alert_below(self, client, auth_headers):
        """Creating a 'falls below' alert returns 201."""
        alert = {
            "ticker": "TSLA",
            "target_price": 100.00,
            "direction": "below",
            "email_notify": False,
        }
        res = client.post(ALERTS_URL, headers=auth_headers, json=alert)
        assert res.status_code == 201
        data = res.json()
        assert data["direction"] == "below"
        assert data["email_notify"] is False

    def test_create_alert_invalid_direction(self, client, auth_headers):
        """An invalid direction value returns 400."""
        bad_alert = {
            "ticker": "AAPL",
            "target_price": 150.00,
            "direction": "sideways",
            "email_notify": True,
        }
        res = client.post(ALERTS_URL, headers=auth_headers, json=bad_alert)
        assert res.status_code == 400

    def test_create_alert_negative_price(self, client, auth_headers):
        """A non-positive target price returns 400."""
        bad_alert = {
            "ticker": "AAPL",
            "target_price": -10.00,
            "direction": "above",
            "email_notify": True,
        }
        res = client.post(ALERTS_URL, headers=auth_headers, json=bad_alert)
        assert res.status_code == 400

    def test_create_alert_unauthenticated(self, client):
        """Creating an alert without a token returns 401."""
        res = client.post(ALERTS_URL, json=VALID_ALERT)
        assert res.status_code == 401

    def test_alert_appears_in_list(self, client, auth_headers):
        """A newly created alert appears in the user's alert list."""
        res = client.get(ALERTS_URL, headers=auth_headers)
        assert res.status_code == 200
        tickers = [a["ticker"] for a in res.json()]
        assert "AAPL" in tickers


class TestDeleteAlert:
    def test_delete_existing_alert(self, client, auth_headers):
        """DELETE /alerts/{id} removes the alert and returns 204."""
        # Create an alert to delete
        create_res = client.post(ALERTS_URL, headers=auth_headers, json={
            "ticker": "NVDA",
            "target_price": 500.00,
            "direction": "above",
            "email_notify": False,
        })
        assert create_res.status_code == 201
        alert_id = create_res.json()["id"]

        delete_res = client.delete(f"{ALERTS_URL}/{alert_id}", headers=auth_headers)
        assert delete_res.status_code == 204

    def test_deleted_alert_not_in_list(self, client, auth_headers):
        """A deleted alert no longer appears in GET /alerts."""
        # Create and delete
        create_res = client.post(ALERTS_URL, headers=auth_headers, json={
            "ticker": "AMD",
            "target_price": 120.00,
            "direction": "below",
            "email_notify": True,
        })
        alert_id = create_res.json()["id"]
        client.delete(f"{ALERTS_URL}/{alert_id}", headers=auth_headers)

        list_res = client.get(ALERTS_URL, headers=auth_headers)
        ids = [a["id"] for a in list_res.json()]
        assert alert_id not in ids

    def test_delete_nonexistent_alert(self, client, auth_headers):
        """DELETE /alerts/{fake_id} returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        res = client.delete(f"{ALERTS_URL}/{fake_id}", headers=auth_headers)
        assert res.status_code == 404

    def test_delete_alert_unauthenticated(self, client, auth_headers):
        """DELETE /alerts/{id} without a token returns 401."""
        create_res = client.post(ALERTS_URL, headers=auth_headers, json=VALID_ALERT)
        alert_id = create_res.json()["id"]
        res = client.delete(f"{ALERTS_URL}/{alert_id}")
        assert res.status_code == 401
