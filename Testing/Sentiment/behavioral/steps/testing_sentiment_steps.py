from __future__ import annotations

import sys
from pathlib import Path

from behave import given, when, then
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Ensure Backend/ is importable *before* importing `app.*`.
_BACKEND_DIR = Path(__file__).resolve().parents[4] / "Backend"
if _BACKEND_DIR.exists():
    sys.path.insert(0, str(_BACKEND_DIR))

from app.api.sentiment import router as sentiment_router
from app.db.main import get_db

from Testing.Sentiment._fakes import FakeDB


def _build_test_client(db: FakeDB) -> TestClient:
    app = FastAPI()
    app.include_router(sentiment_router, prefix="/api")

    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


@given("the sentiment indicators data store is empty")
def step_given_empty_store(context):
    context.db = FakeDB()
    context.client = _build_test_client(context.db)


@given('the sentiment indicators data store has a snapshot for "{ticker}" with 30d return {ret_30d:f}')
def step_given_snapshot(context, ticker: str, ret_30d: float):
    context.db = FakeDB()
    context.db.seed_snapshots(
        [
            {
                "id": "1",
                "ticker": ticker,
                "snapshot_date": "2022-02-28",
                "close_price": 123.45,
                "return_30d": ret_30d,
                "return_120d": 0.0,
                "return_360d": 0.0,
            }
        ]
    )
    context.client = _build_test_client(context.db)


@given('the sentiment indicators data store has {count:d} rows for ticker "{ticker}"')
def step_given_delete_rowcount(context, count: int, ticker: str):
    context.db = FakeDB()
    context.db.seed_delete_rowcount(count)
    context.client = _build_test_client(context.db)


@when("I request sentiment indicators")
def step_when_get_indicators(context):
    context.response = context.client.get("/api/sentiment/indicators")


@when('I request sentiment indicators for "{ticker_query}"')
def step_when_get_indicators_filtered(context, ticker_query: str):
    context.response = context.client.get(
        "/api/sentiment/indicators", params={"ticker": ticker_query}
    )


@when('I delete sentiment indicators for ticker "{ticker}"')
def step_when_delete_indicators(context, ticker: str):
    context.response = context.client.delete(f"/api/sentiment/indicators/{ticker}")


@then("the response status code is 200")
def step_then_status_200(context):
    assert context.response.status_code == 200


@then("the response is an empty list")
def step_then_empty_list(context):
    assert context.response.json() == []


@then('the response contains ticker "{ticker}"')
def step_then_contains_ticker(context, ticker: str):
    payload = context.response.json()
    assert isinstance(payload, list)
    assert any(item.get("ticker") == ticker for item in payload)


@then('the indicator "{key}" is "{label}"')
def step_then_indicator_is(context, key: str, label: str):
    payload = context.response.json()
    assert payload and isinstance(payload, list)
    indicators = payload[0]["indicators"]
    assert indicators[key] == label


@then('the deleted count is {count:d}')
def step_then_deleted_count(context, count: int):
    payload = context.response.json()
    assert payload["deleted"] == count
