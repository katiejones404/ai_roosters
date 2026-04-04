"""
test_portfolio.py
Behavioral tests for portfolio management endpoints.

Notes
-----
Tests cover adding positions, retrieving individual items, updating quantities
and prices, and removing positions. The portfolio summary endpoint is excluded
because it requires a populated stocks price table not available in unit tests.
"""
import pytest


PORTFOLIO_URL = "/api/portfolio"

APPLE_POSITION = {
    "ticker": "AAPL",
    "quantity": 10.0,
    "avg_price": 150.00,
}

TSLA_POSITION = {
    "ticker": "TSLA",
    "quantity": 5.0,
    "avg_price": 200.00,
}


class TestEmptyPortfolio:
    def test_empty_portfolio_returns_list(self, client, auth_headers):
        """GET /portfolio returns an empty list for a new user with no positions."""
        res = client.get(PORTFOLIO_URL, headers=auth_headers)
        assert res.status_code == 200
        assert isinstance(res.json(), list)


class TestAddToPortfolio:
    def test_add_position_success(self, client, auth_headers):
        """Adding a new position returns 201 with the created item."""
        res = client.post(PORTFOLIO_URL, headers=auth_headers, json=APPLE_POSITION)
        assert res.status_code == 201
        data = res.json()
        assert data["ticker"] == "AAPL"
        assert float(data["quantity"]) == 10.0
        assert float(data["avg_price"]) == 150.00

    def test_add_same_ticker_averages_price(self, client, auth_headers):
        """Adding shares of an existing ticker increases quantity and averages price."""
        # AAPL already has 10 shares at $150 from prior test
        additional = {"ticker": "AAPL", "quantity": 10.0, "avg_price": 200.00}
        res = client.post(PORTFOLIO_URL, headers=auth_headers, json=additional)
        assert res.status_code == 201
        data = res.json()
        assert float(data["quantity"]) == 20.0
        # Weighted average: (10*150 + 10*200) / 20 = 175
        assert float(data["avg_price"]) == pytest.approx(175.0, rel=1e-3)

    def test_add_second_ticker(self, client, auth_headers):
        """Adding a different ticker creates a separate position."""
        res = client.post(PORTFOLIO_URL, headers=auth_headers, json=TSLA_POSITION)
        assert res.status_code == 201
        assert res.json()["ticker"] == "TSLA"


class TestGetPortfolioItem:
    def test_get_existing_item(self, client, auth_headers):
        """GET /portfolio/{ticker} returns the matching position."""
        res = client.get(f"{PORTFOLIO_URL}/AAPL", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["ticker"] == "AAPL"

    def test_get_nonexistent_item(self, client, auth_headers):
        """GET /portfolio/{ticker} for an unknown ticker returns 404."""
        res = client.get(f"{PORTFOLIO_URL}/FAKE", headers=auth_headers)
        assert res.status_code == 404

    def test_get_item_unauthenticated(self, client):
        """GET /portfolio/{ticker} without token returns 401."""
        res = client.get(f"{PORTFOLIO_URL}/AAPL")
        assert res.status_code == 401


class TestUpdatePortfolioItem:
    def test_update_quantity(self, client, auth_headers):
        """PUT /portfolio/{ticker} updates the quantity of an existing position."""
        res = client.put(
            f"{PORTFOLIO_URL}/TSLA",
            headers=auth_headers,
            json={"quantity": 15.0},
        )
        assert res.status_code == 200
        assert float(res.json()["quantity"]) == 15.0

    def test_update_avg_price(self, client, auth_headers):
        """PUT /portfolio/{ticker} updates the average price of an existing position."""
        res = client.put(
            f"{PORTFOLIO_URL}/TSLA",
            headers=auth_headers,
            json={"avg_price": 250.00},
        )
        assert res.status_code == 200
        assert float(res.json()["avg_price"]) == 250.00

    def test_update_nonexistent_ticker(self, client, auth_headers):
        """PUT /portfolio/{ticker} for an unknown ticker returns 404."""
        res = client.put(
            f"{PORTFOLIO_URL}/FAKE",
            headers=auth_headers,
            json={"quantity": 5.0},
        )
        assert res.status_code == 404


class TestRemoveFromPortfolio:
    def test_remove_existing_position(self, client, auth_headers):
        """DELETE /portfolio/{ticker} removes the position and returns success."""
        res = client.delete(f"{PORTFOLIO_URL}/TSLA", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"

    def test_position_gone_after_delete(self, client, auth_headers):
        """Deleted ticker returns 404 on subsequent GET."""
        res = client.get(f"{PORTFOLIO_URL}/TSLA", headers=auth_headers)
        assert res.status_code == 404

    def test_remove_nonexistent_ticker(self, client, auth_headers):
        """DELETE /portfolio/{ticker} for a ticker not in portfolio returns 404."""
        res = client.delete(f"{PORTFOLIO_URL}/FAKE", headers=auth_headers)
        assert res.status_code == 404
