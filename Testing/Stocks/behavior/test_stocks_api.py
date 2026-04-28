"""
test_stocks_api.py  -  BEHAVIORAL TESTS
End-to-end API tests for the stocks endpoints using an in-memory SQLite database.
Covers stock listing, price history retrieval, and the 2020-01-01 return cutoff policy.
"""
from sqlalchemy import text
from app.api.stocks import router


def seed_stocks(db):
    db.execute(text("""
        INSERT INTO stocks (ticker, date, close, adjusted_close, return_1d, return_30d, return_120d, return_360d)
        VALUES
          ('AAPL', '2019-12-30', 100.0, 100.0, 0.01, 0.10, 0.20, 0.30),
          ('AAPL', '2019-12-31', 98.0, 98.0, 0.02, 0.11, 0.21, 0.31),
          ('AAPL', '2020-01-02', 101.0, 101.0, 0.03, 0.12, 0.22, 0.32),
          ('MSFT', '2025-01-01', 200.0, 200.0, 0.03, 0.12, 0.22, 0.32)
    """))
    db.commit()


def test_list_stocks_returns_distinct_sorted(client, sqlite_session):
    seed_stocks(sqlite_session)

    resp = client.get("/api/stocks")
    assert resp.status_code == 200
    assert resp.json() == [{"ticker": "AAPL"}, {"ticker": "MSFT"}]


def test_get_stock_prices_returns_rows(client, sqlite_session):
    seed_stocks(sqlite_session)

    resp = client.get("/api/stocks/AAPL/prices")
    assert resp.status_code == 200
    rows = resp.json()

    assert len(rows) == 3
    assert rows[0]["ticker"] == "AAPL"
    assert rows[0]["date"] == "2019-12-30"
    assert rows[0]["close"] == 100.0
    assert rows[0]["adjusted_close"] == 100.0
    assert rows[0]["return_1d"] is None


def test_get_stock_prices_applies_date_filters(client, sqlite_session):
    seed_stocks(sqlite_session)

    resp = client.get("/api/stocks/AAPL/prices?start_date=2020-01-02&end_date=2020-01-02")
    assert resp.status_code == 200
    rows = resp.json()

    assert len(rows) == 1
    assert rows[0]["date"] == "2020-01-02"


def test_get_stock_prices_pre_2020_returns_are_null(client, sqlite_session):
    seed_stocks(sqlite_session)

    resp = client.get("/api/stocks/AAPL/prices")
    assert resp.status_code == 200
    rows = resp.json()

    assert rows[1]["date"] == "2019-12-31"
    assert rows[1]["return_1d"] is None
    assert rows[1]["return_30d"] is None

    assert rows[2]["date"] == "2020-01-02"
    assert rows[2]["return_1d"] is not None


def test_get_stock_prices_404_when_no_data(client):
    resp = client.get("/api/stocks/NVDA/prices")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "No price data found for this ticker"
