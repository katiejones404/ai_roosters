# for current iteration of news_ingest.py
from __future__ import annotations

import csv
import tempfile
from typing import List, Dict

import pytest

from backend.app.services import news_ingest as ni


def make_fake_article(url="https://example.com/a", published_at="2023-01-01T00:00:00+00:00"):
    return {
        "published_at": published_at,
        "title": "Fake Title For Testing",
        "description": "Fake description",
        "url": url,
        "inserted_at": ni.now_utc_iso(),
    }


def test_main_writes_csv_with_stubbed_collector(monkeypatch, tmp_path):
    """
    Behavioral-style test: stub out collect_for_year_concurrent to avoid network,
    then run ni.main() (with monkeypatched parse_args) and assert CSV created.
    """

    fake_rows = [
        make_fake_article(url="https://example.com/a"),
        make_fake_article(url="https://example.com/b", published_at="2023-02-02T00:00:00+00:00"),
    ]

    # 
    def fake_collect_for_year_concurrent(*args, **kwargs) -> List[Dict]:
        return fake_rows

    monkeypatch.setattr(ni, "collect_for_year_concurrent", fake_collect_for_year_concurrent)

    # 
    class FakeArgs:
        output = str(tmp_path / "out.csv")
        years = [2023]
        articles_per_year = 10
        files_per_year = 1
        max_workers = 1
        keywords = ni.KEYWORDS_DEFAULT
        domains = ni.SOURCE_DOMAINS_DEFAULT
        force_refresh_master = False
        verbose = False

    monkeypatch.setattr(ni, "parse_args", lambda: FakeArgs())

    # Run main 
    ni.main()

    out = tmp_path / "out.csv"
    assert out.exists()
    with open(out, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        assert len(rows) == len(fake_rows)
        assert {r["url"] for r in rows} == {fake_rows[0]["url"], fake_rows[1]["url"]}
