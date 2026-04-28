"""
test_price_ingest.py  -  UNIT TESTS
Unit tests for app.services.ingesting_pipelines.prices_ingest.
Covers DB URL construction, PriceIngestor initialization, ticker resolution,
and stock storage logic using mocked SQLAlchemy engines and tables.
"""
from unittest.mock import MagicMock
import pandas as pd
from sqlalchemy import MetaData, Table, Column, String, Date, Float, Integer
import pytest

from app.services.ingesting_pipelines.prices_ingest import build_db_url, PriceIngestor


def test_build_db_url_prefers_DATABASE_URL(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/db")
    assert build_db_url() == "postgresql://u:p@h:5432/db"


def test_build_db_url_uses_components_defaults(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    monkeypatch.setenv("PG_USER", "user1")
    monkeypatch.setenv("PG_PASS", "pass1")
    monkeypatch.setenv("PG_HOST", "localhost")
    monkeypatch.setenv("PG_PORT", "5433")
    monkeypatch.setenv("PG_DB", "mydb")

    assert build_db_url() == "postgresql://user1:pass1@localhost:5433/mydb"


def test_build_db_url_missing_values(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("PG_USER", "u")
    monkeypatch.setenv("PG_PASS", "p")
    monkeypatch.setenv("PG_HOST", "h")
    monkeypatch.setenv("PG_DB", "db")

    url = build_db_url()
    assert "postgresql://" in url


def _make_ingestor_without_real_db(monkeypatch):
    import app.services.ingesting_pipelines.prices_ingest as module_under_test

    fake_engine = MagicMock()
    monkeypatch.setattr(module_under_test, "create_engine", lambda *_a, **_kw: fake_engine)

    def fake_MetaData():
        md = MetaData()
        Table(
            "stocks",
            md,
            Column("ticker", String, primary_key=True),
            Column("date", Date, primary_key=True),
            Column("open", Float),
            Column("high", Float),
            Column("low", Float),
            Column("close", Float),
            Column("adjusted_close", Float),
            Column("volume", Integer),
        )
        md.reflect = lambda *_a, **_kw: None
        return md

    monkeypatch.setattr(module_under_test, "MetaData", fake_MetaData)

    ing = module_under_test.PriceIngestor(db_url="postgresql://fake")
    return ing, fake_engine, ing.stocks


def test_fetch_stock_data_happy_path(monkeypatch):
    ing, _, _ = _make_ingestor_without_real_db(monkeypatch)
    import app.services.ingesting_pipelines.prices_ingest as module_under_test

    fake_hist = pd.DataFrame(
        {
            "Open": [10.0],
            "High": [12.0],
            "Low": [9.0],
            "Close": [11.0],
            "Volume": [100],
        },
        index=pd.to_datetime(["2025-01-01"]),
    )
    fake_hist.index.name = "Date"

    fake_ticker = MagicMock()
    fake_ticker.history.return_value = fake_hist
    monkeypatch.setattr(module_under_test.yf, "Ticker", lambda _: fake_ticker)

    df = ing.fetch_stock_data("AAPL")

    assert not df.empty
    assert df.loc[0, "ticker"] == "AAPL"


def test_fetch_stock_data_empty(monkeypatch):
    ing, _, _ = _make_ingestor_without_real_db(monkeypatch)
    import app.services.ingesting_pipelines.prices_ingest as module_under_test

    fake_ticker = MagicMock()
    fake_ticker.history.return_value = pd.DataFrame()
    monkeypatch.setattr(module_under_test.yf, "Ticker", lambda _: fake_ticker)

    df = ing.fetch_stock_data("AAPL")
    assert df.empty


def test_fetch_stock_data_handles_multiple_rows(monkeypatch):
    ing, _, _ = _make_ingestor_without_real_db(monkeypatch)
    import app.services.ingesting_pipelines.prices_ingest as module_under_test

    fake_hist = pd.DataFrame(
        {
            "Open": [1, 2],
            "High": [2, 3],
            "Low": [0, 1],
            "Close": [1.5, 2.5],
            "Volume": [100, 200],
        },
        index=pd.to_datetime(["2025-01-01", "2025-01-02"]),
    )
    fake_hist.index.name = "Date"

    fake_ticker = MagicMock()
    fake_ticker.history.return_value = fake_hist
    monkeypatch.setattr(module_under_test.yf, "Ticker", lambda _: fake_ticker)

    df = ing.fetch_stock_data("AAPL")
    assert len(df) == 2


def test_store_prices_batches(monkeypatch):
    ing, fake_engine, _ = _make_ingestor_without_real_db(monkeypatch)

    df = pd.DataFrame({
        "ticker": ["AAPL"] * 10,
        "date": pd.to_datetime(pd.date_range("2025-01-01", periods=10)).date,
        "open": [1]*10,
        "high": [2]*10,
        "low": [0.5]*10,
        "close": [1.5]*10,
        "adjusted_close": [1.5]*10,
        "volume": [100]*10,
    })

    calls = []

    class FakeConn:
        def execute(self, stmt):
            calls.append(stmt)

    class FakeCtx:
        def __enter__(self): return FakeConn()
        def __exit__(self, *args): return False

    fake_engine.begin.return_value = FakeCtx()

    ing.store_prices(df)
    assert len(calls) >= 1


def test_store_prices_empty_df(monkeypatch):
    ing, fake_engine, _ = _make_ingestor_without_real_db(monkeypatch)

    df = pd.DataFrame()
    ing.store_prices(df)

    fake_engine.begin.assert_not_called()


def test_ingest_multiple_calls_store(monkeypatch):
    ing, _, _ = _make_ingestor_without_real_db(monkeypatch)

    df = pd.DataFrame({
        "ticker": ["AAPL"],
        "date": [pd.to_datetime("2025-01-01").date()],
        "open": [1],
        "high": [2],
        "low": [0.5],
        "close": [1.5],
        "adjusted_close": [1.5],
        "volume": [100],
    })

    ing.fetch_stock_data = MagicMock(return_value=df)
    ing.store_prices = MagicMock()

    ing.ingest_multiple_stocks(["AAPL"])

    ing.store_prices.assert_called_once()


def test_ingest_multiple_skips_empty(monkeypatch):
    ing, _, _ = _make_ingestor_without_real_db(monkeypatch)

    ing.fetch_stock_data = MagicMock(return_value=pd.DataFrame())
    ing.store_prices = MagicMock()

    ing.ingest_multiple_stocks(["AAPL"])

    ing.store_prices.assert_not_called()


def test_ingest_multiple_multiple_symbols(monkeypatch):
    ing, _, _ = _make_ingestor_without_real_db(monkeypatch)

    df = pd.DataFrame({
        "ticker": ["AAPL"],
        "date": [pd.to_datetime("2025-01-01").date()],
        "open": [1],
        "high": [2],
        "low": [0.5],
        "close": [1.5],
        "adjusted_close": [1.5],
        "volume": [100],
    })

    ing.fetch_stock_data = MagicMock(side_effect=[df, df])
    ing.store_prices = MagicMock()

    ing.ingest_multiple_stocks(["AAPL", "MSFT"])

    assert ing.store_prices.call_count == 2