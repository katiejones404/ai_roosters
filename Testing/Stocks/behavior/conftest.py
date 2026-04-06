"""
Behavioral test fixtures for the Stocks API.
Requires FastAPI + compatible Pydantic (runs in Docker / CI).
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.stocks import router as stocks_router
import app.api.stocks as stocks_module


@pytest.fixture(scope="function")
def sqlite_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE stocks (
                ticker TEXT NOT NULL,
                date   DATE NOT NULL,
                close  REAL,
                adjusted_close REAL,
                return_1d REAL,
                return_30d REAL,
                return_120d REAL,
                return_360d REAL,
                UNIQUE(ticker, date)
            )
        """))

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def client(sqlite_session):
    app = FastAPI()
    app.include_router(stocks_router, prefix="/api")

    def override_get_db():
        yield sqlite_session

    app.dependency_overrides[stocks_module.get_db] = override_get_db
    return TestClient(app)
