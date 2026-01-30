# Testing/News/test_utils.py
from __future__ import annotations

import re
import math
from decimal import Decimal

import pytest

# import module
from app.services import news_ingest as ni


@pytest.mark.parametrize(
    "text,keywords,expected",
    [
        ("Company reports earnings", ["earnings"], True),
        ("This is unrelated", ["stock"], False),
        ("WALL STREET surges", ["wall street"], True),
        ("", ["anything"], False),
        (None, ["anything"], False),
    ],
)
def test_keyword_match_param(text, keywords, expected):
    # keyword_match expects a str; when passing None we ensure it False
    if text is None:
        assert ni.keyword_match(text, keywords) is False
    else:
        assert ni.keyword_match(text, keywords) is expected


def test_domain_match_examples():
    assert ni.domain_match("https://www.reuters.com/article/1", ["reuters.com"])
    assert ni.domain_match("https://sub.WSJ.com/path", ["wsj.com"])
    # empty domain list = allow all
    assert ni.domain_match("https://any.site/a", [])
    # malformed url handled
    assert ni.domain_match("not-a-url", ["example.com"]) is False


def test_extract_gkg_path_from_line():
    line = "http://data.gdeltproject.org/gdeltv2/20230101.gkg.csv.zip otherstuff"
    p = ni.extract_gkg_path_from_line(line)
    assert p is not None and p.lower().endswith(".gkg.csv.zip")

    assert ni.extract_gkg_path_from_line("no matching token here") is None
    assert ni.extract_gkg_path_from_line("SOME.PATH/FILE.GKG.CSV.ZIP") is not None


def test_score_title_candidate_rejects_machine_tokens_and_short():
    assert ni.score_title_candidate("") == float("-inf")
    assert ni.score_title_candidate("a1:10,b2:3") == float("-inf")
    # plausible title gets positive good score
    s = "Acme Corp Reports Quarterly Profit, Shares Up"
    score = ni.score_title_candidate(s)
    assert isinstance(score, float)
    assert score > 0


def test_get_description_from_row_truncation_and_formatting():
    row = [""] * 10
    row[7] = "ECON_FINANCE;STOCKS;MARKET;COMPANIES"
    desc = ni.get_description_from_row(row)
    # Should convert underscores/caps and use commas
    assert ("Stocks" in desc) or ("Market" in desc)

    long_row = [""] * 10
    long_row[7] = "TAG;" + ("A" * 500)
    desc2 = ni.get_description_from_row(long_row)
    assert len(desc2) <= 203  # truncated with "..."


def test_get_title_from_row_prefers_priority_and_slug_fallback():
    # row with page title in column 16
    row = [""] * 30
    row[4] = "https://example.com/companies/acme-reports-profit-2023.html"
    row[16] = "Acme Reports Record Profit For Q4"
    title = ni.get_title_from_row(row)
    assert title is not None and "Acme" in title

    # If title is too low-scoring, fallback might be used only if score high enough
    row2 = [""] * 30
    row2[4] = "https://example.com/short/xx"
    row2[16] = "x x"
    assert ni.get_title_from_row(row2) is None
