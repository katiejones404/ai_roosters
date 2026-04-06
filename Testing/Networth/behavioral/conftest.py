"""
conftest.py - Networth behavioral test fixtures.

Creates an in-memory SQLite database with the networth tables and provides
a FastAPI TestClient wired to a registered, logged-in test user.
"""

from __future__ import annotations

import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def _configure_paths() -> None:
    here = os.path.abspath(os.path.dirname(__file__))
    repo_root = os.path.abspath(os.path.join(here, "..", "..", ".."))
    backend_root = os.path.join(repo_root, "backend")
    for candidate in ("/app", backend_root, repo_root):
        if os.path.isdir(candidate) and candidate not in sys.path:
            sys.path.insert(0, candidate)


_configure_paths()

from app.db.base import Base
from app.db.main import get_db
from app.models.models import User, Portfolio, PriceAlert
from app.api import auth as auth_module
from app.api import networth as networth_module

_TEST_DB_URL = "sqlite:///:memory:"
_engine = create_engine(
    _TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

# Create ORM tables
Base.metadata.create_all(
    bind=_engine,
    tables=[User.__table__, Portfolio.__table__, PriceAlert.__table__],
)

# Create networth-specific tables  (not in ORM models,  raw SQL)
with _engine.begin() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS networth_assets (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            balance REAL NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS networth_liabilities (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            balance REAL NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS networth_snapshots (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            snapshot_date TEXT NOT NULL,
            portfolio_value REAL DEFAULT 0,
            total_assets REAL DEFAULT 0,
            total_liabilities REAL DEFAULT 0,
            net_worth REAL DEFAULT 0,
            UNIQUE(user_id, snapshot_date)
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS stocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            close REAL,
            adjusted_close REAL,
            open REAL,
            high REAL,
            low REAL,
            volume INTEGER,
            return_1d REAL,
            return_30d REAL,
            return_120d REAL,
            return_360d REAL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS portfolio (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            ticker TEXT NOT NULL,
            quantity REAL NOT NULL,
            avg_price REAL NOT NULL,
            added_at TEXT DEFAULT (datetime('now'))
        )
    """))


def _override_get_db():
    db = _Session()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def client():
    app = FastAPI()
    app.include_router(auth_module.router, prefix="/api")
    app.include_router(networth_module.router, prefix="/api")
    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


@pytest.fixture(scope="module")
def auth_headers(client):
    creds = {
        "email": "nw_beh@example.com", "username": "nw_beh_user",
        "password": "NwPass99!", "confirm_password": "NwPass99!",
    }
    client.post("/api/auth/register", json=creds)
    res = client.post("/api/auth/login",
                      json={"email": creds["email"], "password": creds["password"]})
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture(scope="module")
def other_headers(client):
    creds = {
        "email": "nw_other@example.com", "username": "nw_other_user",
        "password": "NwOther99!", "confirm_password": "NwOther99!",
    }
    client.post("/api/auth/register", json=creds)
    res = client.post("/api/auth/login",
                      json={"email": creds["email"], "password": creds["password"]})
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['access_token']}"}
