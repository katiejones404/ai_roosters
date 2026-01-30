from sqlalchemy import text
from app.api.stocks import router


def seed_stocks(db):
    db.execute(text("""
        INSERT INTO stocks (ticker, date, close, adjusted_close, return_1d, return_30d, return_120d, return_360d)
        VALUES
          ('AAPL', '2025-01-01', 100.0, 100.0, 0.01, 0.10, 0.20, 0.30),
          ('AAPL', '2025-01-02', 101.0, 101.0, 0.02, 0.11, 0.21, 0.31),
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

    assert len(rows) == 2
    assert rows[0]["ticker"] == "AAPL"
    assert rows[0]["date"] == "2025-01-01"
    assert rows[0]["close"] == 100.0
    assert rows[0]["adjusted_close"] == 100.0
    assert rows[0]["return_1d"] == 0.01


def test_get_stock_prices_applies_date_filters(client, sqlite_session):
    seed_stocks(sqlite_session)

    resp = client.get("/api/stocks/AAPL/prices?start_date=2025-01-02&end_date=2025-01-02")
    assert resp.status_code == 200
    rows = resp.json()

    assert len(rows) == 1
    assert rows[0]["date"] == "2025-01-02"


def test_get_stock_prices_404_when_no_data(client):
    resp = client.get("/api/stocks/NVDA/prices")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "No price data found for this ticker"
