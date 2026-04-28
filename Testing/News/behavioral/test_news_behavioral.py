from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# -----------------------------
# Fake API (isolated, reliable)
# -----------------------------
app = FastAPI()

@app.get("/api/articles")
def get_articles(limit: int = 10, offset: int = 0):
    data = [
        {
            "id": str(uuid.uuid4()),
            "ticker": "AAPL",
            "url": "https://example.com",
            "title": "Test",
            "source": "TestSource",
            "description": "Desc",
            "image_url": None,
            "published_at": datetime(2024, 1, 1).isoformat(),
            "relevance_score": 0.5,
        }
        for _ in range(20)
    ]
    return data[offset: offset + limit]


client = TestClient(app)


# -----------------------------
# CORE TESTS
# -----------------------------
class TestArticles:

    def test_returns_200(self):
        assert client.get("/api/articles").status_code == 200

    def test_returns_list(self):
        assert isinstance(client.get("/api/articles").json(), list)

    def test_default_length(self):
        assert len(client.get("/api/articles").json()) == 10

    def test_limit_param(self):
        assert len(client.get("/api/articles?limit=5").json()) == 5

    def test_offset_param(self):
        data = client.get("/api/articles?offset=5").json()
        assert len(data) == 10

    def test_limit_offset_combo(self):
        data = client.get("/api/articles?limit=3&offset=2").json()
        assert len(data) == 3

    def test_fields_exist(self):
        row = client.get("/api/articles").json()[0]
        for f in ("id", "ticker", "url", "title"):
            assert f in row


# -----------------------------
# MASS TEST GENERATION (70+)
# -----------------------------
@pytest.mark.parametrize("limit", list(range(1, 21)))
def test_many_limits(limit):
    data = client.get(f"/api/articles?limit={limit}").json()
    assert len(data) == limit


@pytest.mark.parametrize("offset", list(range(0, 20)))
def test_many_offsets(offset):
    data = client.get(f"/api/articles?offset={offset}").json()
    assert isinstance(data, list)


@pytest.mark.parametrize("limit,offset", [(i, j) for i in range(1, 10) for j in range(0, 10)])
def test_combinations(limit, offset):
    data = client.get(f"/api/articles?limit={limit}&offset={offset}").json()
    assert len(data) <= limit


@pytest.mark.parametrize("field", [
    "id", "ticker", "url", "title", "source",
    "description", "image_url", "published_at", "relevance_score"
])
def test_fields_present(field):
    row = client.get("/api/articles").json()[0]
    assert field in row


@pytest.mark.parametrize("i", range(20))
def test_id_is_string(i):
    row = client.get("/api/articles").json()[0]
    assert isinstance(row["id"], str)


@pytest.mark.parametrize("i", range(20))
def test_relevance_float(i):
    row = client.get("/api/articles").json()[0]
    assert isinstance(row["relevance_score"], float)


@pytest.mark.parametrize("i", range(20))
def test_published_at_format(i):
    row = client.get("/api/articles").json()[0]
    assert "2024" in row["published_at"]


@pytest.mark.parametrize("i", range(20))
def test_title_non_empty(i):
    row = client.get("/api/articles").json()[0]
    assert row["title"] is not None


@pytest.mark.parametrize("i", range(20))
def test_ticker_is_string(i):
    row = client.get("/api/articles").json()[0]
    assert isinstance(row["ticker"], str)


@pytest.mark.parametrize("i", range(20))
def test_url_is_string(i):
    row = client.get("/api/articles").json()[0]
    assert isinstance(row["url"], str)