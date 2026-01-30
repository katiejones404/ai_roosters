from unittest.mock import MagicMock
import pandas as pd
from sqlalchemy import MetaData, Table, Column, String, Date, Float, Integer
from app.services.prices_ingest import build_db_url, PriceIngestor


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

def _make_ingestor_without_real_db(monkeypatch):
    import app.services.prices_ingest as module_under_test

    fake_engine = MagicMock()
    monkeypatch.setattr(module_under_test, "create_engine", lambda *_a, **_kw: fake_engine)

    def fake_MetaData():
        md = MetaData()

        # Create the table *attached to this md*
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

        # Reflect is called by __init__, so make it a no-op
        md.reflect = lambda *_a, **_kw: None
        return md

    monkeypatch.setattr(module_under_test, "MetaData", fake_MetaData)

    ing = module_under_test.PriceIngestor(db_url="postgresql://fake")
    return ing, fake_engine, ing.stocks


def test_fetch_stock_data_happy_path(monkeypatch):
    ing, _engine, _table = _make_ingestor_without_real_db(monkeypatch)
    import app.services.prices_ingest as module_under_test

    fake_hist = pd.DataFrame(
        {
            "Open": [10.0, 11.0],
            "High": [12.0, 13.0],
            "Low": [9.0, 10.0],
            "Close": [11.0, 12.0],
            "Volume": [100, 200],
        },
        index=pd.to_datetime(["2025-01-01", "2025-01-02"]),
    )
    fake_hist.index.name = "Date"
    fake_ticker = MagicMock()
    fake_ticker.history.return_value = fake_hist
    monkeypatch.setattr(module_under_test.yf, "Ticker", lambda _t: fake_ticker)

    df = ing.fetch_stock_data("AAPL", period="1y")

    assert list(df.columns) == [
        "ticker", "date", "open", "high", "low", "close", "adjusted_close", "volume"
    ]
    assert len(df) == 2
    assert df.loc[0, "ticker"] == "AAPL"
    assert str(type(df.loc[0, "date"])) == "<class 'datetime.date'>"
    assert df.loc[0, "adjusted_close"] == df.loc[0, "close"]


def test_fetch_stock_data_empty_returns_empty_df(monkeypatch):
    ing, _engine, _table = _make_ingestor_without_real_db(monkeypatch)
    import app.services.prices_ingest as module_under_test

    fake_ticker = MagicMock()
    fake_ticker.history.return_value = pd.DataFrame()
    monkeypatch.setattr(module_under_test.yf, "Ticker", lambda _t: fake_ticker)

    df = ing.fetch_stock_data("AAPL", period="1y")
    assert df.empty


def test_store_prices_batches_and_conflict_mode(monkeypatch):
    ing, fake_engine, _table = _make_ingestor_without_real_db(monkeypatch)

    n = 250  
    df = pd.DataFrame({
        "ticker": ["AAPL"] * n,
        "date": pd.to_datetime(pd.date_range("2025-01-01", periods=n)).date,
        "open": [1.0] * n,
        "high": [2.0] * n,
        "low": [0.5] * n,
        "close": [1.5] * n,
        "adjusted_close": [1.5] * n,
        "volume": [100] * n,
    })

    executed = []

    class FakeConn:
        def execute(self, stmt):
            executed.append(stmt)

    class FakeBeginCtx:
        def __enter__(self): return FakeConn()
        def __exit__(self, exc_type, exc, tb): return False

    fake_engine.begin.return_value = FakeBeginCtx()

    ing.store_prices(df, update_existing=False)
    assert len(executed) == 3

    from sqlalchemy.dialects import postgresql
    sql0 = str(executed[0].compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT" in sql0
    assert "DO NOTHING" in sql0

    executed.clear()
    ing.store_prices(df, update_existing=True)
    assert len(executed) == 3

    sql1 = str(executed[0].compile(dialect=postgresql.dialect()))
    assert "DO UPDATE" in sql1


def test_ingest_multiple_stocks_calls_store_only_when_data(monkeypatch):
    ing, _engine, _table = _make_ingestor_without_real_db(monkeypatch)

    good_df = pd.DataFrame({
        "ticker": ["AAPL"],
        "date": [pd.to_datetime("2025-01-01").date()],
        "open": [1.0],
        "high": [2.0],
        "low": [0.5],
        "close": [1.5],
        "adjusted_close": [1.5],
        "volume": [100],
    })

    ing.fetch_stock_data = MagicMock(side_effect=[good_df, pd.DataFrame()])
    ing.store_prices = MagicMock()

    ing.ingest_multiple_stocks(["AAPL", "MSFT"], period="1y", update_existing=False)

    ing.store_prices.assert_called_once()
    args, kwargs = ing.store_prices.call_args
    assert args[0].equals(good_df)
