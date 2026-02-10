# services/alphavantage_ingest.py
from __future__ import annotations
import os
import json
import csv
import logging
from datetime import datetime, date
from typing import List, Optional, Dict, Any
import requests

from dotenv import load_dotenv
from pathlib import Path

# Load .env from repo root
load_dotenv(dotenv_path=Path(__file__).resolve().parents[3] / ".env")


logger = logging.getLogger("alpha_ingest")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(handler)

API_KEY = os.getenv("ALPHAVANTAGE_API_KEY", "demo")
   #put key here
BASE_URL = "https://www.alphavantage.co/query"
CSV_PATH = os.getenv("AV_CSV_PATH", "../../data/article_api_data/news_articles.csv")
REQUESTS_LOG_PATH = os.getenv("AV_REQUESTS_LOG", "../../data/article_api_data/requests_log.json")
REQUESTS_PER_DAY = int(os.getenv("AV_REQUESTS_PER_DAY", "25"))
DEFAULT_LIMIT = int(os.getenv("AV_DEFAULT_LIMIT", "100"))  # per request

# CSV columns (append-only)
CSV_FIELDS = [
    "url",
    "title",
    "description",
    "published_at",
    "sentiment",
    "sentiment_score",
    "prob_pos",
    "prob_neg",
    "prob_neu",
    "source",
    "tickers",
    "fetched_at",
]

# ---------- request-counter helpers ----------
def _today_str() -> str:
    return date.today().isoformat()

def load_requests_log() -> Dict[str, Any]:
    if not os.path.exists(REQUESTS_LOG_PATH):
        return {"date": _today_str(), "count": 0}
    try:
        with open(REQUESTS_LOG_PATH, "r") as f:
            data = json.load(f)
    except Exception:
        return {"date": _today_str(), "count": 0}
    # reset if different day
    if data.get("date") != _today_str():
        return {"date": _today_str(), "count": 0}
    return data

def save_requests_log(log: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(REQUESTS_LOG_PATH) or ".", exist_ok=True)
    with open(REQUESTS_LOG_PATH, "w") as f:
        json.dump(log, f)

def increment_request_count(n: int = 1) -> None:
    log = load_requests_log()
    log["count"] = int(log.get("count", 0)) + n
    log["date"] = _today_str()
    save_requests_log(log)

def remaining_requests() -> int:
    log = load_requests_log()
    return max(0, REQUESTS_PER_DAY - int(log.get("count", 0)))

# ---------- CSV helpers ----------
def ensure_csv_exists():
    os.makedirs(os.path.dirname(CSV_PATH) or ".", exist_ok=True)
    if not os.path.exists(CSV_PATH):
        with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()

def load_existing_urls() -> set:
    ensure_csv_exists()
    urls = set()
    try:
        with open(CSV_PATH, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                if r.get("url"):
                    urls.add(r["url"].strip())
    except FileNotFoundError:
        return set()
    return urls

def append_rows_to_csv(rows: List[Dict[str, Any]]):
    ensure_csv_exists()
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        for r in rows:
            # ensure ordering and missing fields
            out = {k: (r.get(k) if r.get(k) is not None else "") for k in CSV_FIELDS}
            writer.writerow(out)
    logger.info(f"Appended {len(rows)} rows to {CSV_PATH}")

# ---------- AlphaVantage call ----------
import time
import pathlib

RAW_DIR = os.getenv("AV_RAW_DIR", "../../data/article_api_data/raw_responses")
os.makedirs(RAW_DIR, exist_ok=True)
def call_alphavantage_news(tickers: Optional[str]=None, 
                          topics: Optional[str]=None, 
                          time_from: Optional[str]=None,
                          time_to: Optional[str]=None,
                          limit: int = DEFAULT_LIMIT, 
                          max_retries: int = 3) -> Dict[str, Any]:
    """
    Call AlphaVantage NEWS_SENTIMENT with polite throttling and retries.
    Returns the parsed JSON response (may contain 'Information' or 'Note' keys).
    
    time_from: Start time in format YYYYMMDDTHHMM (e.g., "20250101T0000")
    time_to: End time in format YYYYMMDDTHHMM (e.g., "20251231T2359")
    """
    params = {
        "function": "NEWS_SENTIMENT",
        "apikey": API_KEY,
        "limit": limit,
    }
    if tickers:
        params["tickers"] = tickers
    if topics:
        params["topics"] = topics
    if time_from:
        params["time_from"] = time_from
    if time_to:
        params["time_to"] = time_to
    
    attempt = 0
    backoff = 1.1  # base sleep between attempts (seconds) - AV requests ~1/sec
    while attempt <= max_retries:
        attempt += 1
        try:
            resp = requests.get(BASE_URL, params=params, timeout=30)
        except Exception as e:
            logger.exception(f"Network/requests exception on AV call (attempt {attempt}): {e!r}")
            if attempt > max_retries:
                raise
            time.sleep(backoff)
            backoff *= 2
            continue

        # try parse JSON; safe-fallback to raw text
        try:
            parsed = resp.json()
        except Exception:
            parsed = {"_raw_text": resp.text}

        # save raw JSON for debugging
        safe_name = (tickers or "global").replace(",", "_").replace(":", "_").replace(" ", "_")
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        out_path = pathlib.Path(RAW_DIR) / f"{safe_name}_{ts}_attempt{attempt}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(parsed, f, indent=2)
        logger.info(f"Saved raw AV response to {out_path}")

        # If response includes an API-level message, log it and retry with backoff
        if isinstance(parsed, dict) and any(k in parsed for k in ("Information", "Note", "Error Message")):
            msg_key = next(k for k in ("Information", "Note", "Error Message") if k in parsed)
            logger.warning(f"AlphaVantage returned {msg_key}: {parsed[msg_key]}")
            # If we've retried enough, return the parsed payload for caller to inspect and break
            if attempt > max_retries:
                logger.error("Max retries exhausted; returning last response for inspection.")
                time.sleep(1.1)  # polite spacing before returning
                return parsed
            # exponential backoff before retrying
            time.sleep(backoff)
            backoff *= 2
            continue

        # Polite spacing between calls (AV recommends ~1 request/sec)
        time.sleep(1.1)
        # At this point, parsed is likely a feed or a valid JSON; return it
        return parsed

    # If we exit loop unexpectedly, return last parsed
    return parsed
def extract_articles_from_av_response(resp_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    AlphaVantage response structures vary slightly; this function is defensive.
    It returns a list of article dicts with the CSV_FIELDS keys.
    """
    out = []
    # AlphaVantage commonly returns top-level key "feed" or "items" or "data" or "articles"
    candidates = []
    for key in ("feed", "items", "data", "articles", "news"):
        if isinstance(resp_json.get(key), list):
            candidates = resp_json.get(key)
            break
    
    # fallback: sometimes response has 'feed' nested under 'items' etc; be flexible
    if not candidates and isinstance(resp_json, dict):
        # try to find the first list value
        for v in resp_json.values():
            if isinstance(v, list):
                candidates = v
                break
    
    for a in candidates:
        # robust field extraction with multiple possible names
        url = a.get("url") or a.get("link") or a.get("uri") or a.get("id")
        title = a.get("title") or a.get("headline") or ""
        description = a.get("summary") or a.get("description") or a.get("body") or ""
        
        # published time - try multiple possible keys, convert to ISO if possible
        pub = a.get("time_published") or a.get("published_at") or a.get("published") or a.get("date")
        if pub:
            try:
                # many AV responses use ISO or RFC; normalize:
                published_at = datetime.fromisoformat(pub).isoformat()
            except Exception:
                # fallback, keep raw string
                published_at = str(pub)
        else:
            published_at = ""
        
        # sentiment - AV returns overall_sentiment_label and scores under 'overall_sentiment_score' etc
        sentiment = a.get("overall_sentiment_label") or a.get("sentiment") or a.get("overall_sentiment") or ""
        sentiment_score = a.get("overall_sentiment_score") or a.get("sentiment_score") or None
        
        # prob_pos/prob_neg/prob_neu may be under 'sentiment_scores' or 'sentiment' object
        prob_pos = None
        prob_neg = None
        prob_neu = None
        # attempt structured extraction
        sblock = a.get("sentiment") if isinstance(a.get("sentiment"), dict) else a.get("sentiment_scores") or a.get("sentiment_score")
        if isinstance(sblock, dict):
            prob_pos = sblock.get("pos") or sblock.get("prob_pos") or sblock.get("positive")
            prob_neg = sblock.get("neg") or sblock.get("prob_neg") or sblock.get("negative")
            prob_neu = sblock.get("neu") or sblock.get("prob_neu") or sblock.get("neutral")
        
        # FIXED: Extract tickers from ticker_sentiment array
        tickers = []
        ticker_sentiment = a.get("ticker_sentiment") or []
        if isinstance(ticker_sentiment, list):
            tickers = [item.get("ticker") for item in ticker_sentiment if item.get("ticker")]
        
        source = a.get("source") or a.get("publisher") or ""
        
        out.append({
            "url": url or "",
            "title": title,
            "description": description,
            "published_at": published_at,
            "sentiment": sentiment.lower() if isinstance(sentiment, str) else sentiment,
            "sentiment_score": sentiment_score,
            "prob_pos": prob_pos,
            "prob_neg": prob_neg,
            "prob_neu": prob_neu,
            "source": source,
            "tickers": ",".join(tickers) if tickers else "",  # Join tickers with comma
            "fetched_at": datetime.utcnow().isoformat(),
        })
    
    return out

# ---------- Public entry ----------

def ingest_for_tickers(tickers: List[str], 
                      topics: Optional[List[str]] = None, 
                      time_from: Optional[str] = None,
                      time_to: Optional[str] = None,
                      limit: int = DEFAULT_LIMIT):
    """
    tickers: list of ticker strings (e.g. ["AAPL","BP"])
    topics: optional list of topics (e.g. ["technology"])
    time_from: Start time in format YYYYMMDDTHHMM (e.g., "20250101T0000")
    time_to: End time in format YYYYMMDDTHHMM (e.g., "20251231T2359")
    This function will iterate tickers and append new rows to CSV (dedup by url).
    It will not exceed REQUESTS_PER_DAY and will stop early if quota exhausted.
    Only saves articles that actually mention the requested ticker.
    """
    remaining = remaining_requests()
    if remaining <= 0:
        logger.warning("No remaining API requests for today. Exiting.")
        return
    
    existing_urls = load_existing_urls()
    to_append: List[Dict[str, Any]] = []
    requests_made = 0
    
    for t in tickers:
        if remaining <= 0:
            logger.warning("Reached daily request quota while iterating tickers.")
            break
        
        q_ticker = t.strip().upper()
        resp = call_alphavantage_news(tickers=q_ticker, 
                                     topics=topics,
                                     time_from=time_from,
                                     time_to=time_to,
                                     limit=limit)
        
        if isinstance(resp, dict) and any(k in resp for k in ("Information", "Note", "Error Message")):
            logger.warning(f"AlphaVantage signaled rate/limit message for {q_ticker}; stopping further ticker requests for today.")
            break
        
        requests_made += 1
        remaining -= 1
        
        articles = extract_articles_from_av_response(resp)
        new_articles_for_t = []
        
        for art in articles:
            url = (art.get("url") or "").strip()
            
            # Check if this article actually mentions the ticker we searched for
            article_tickers = art.get("tickers", "").split(",")
            article_tickers = [ticker.strip().upper() for ticker in article_tickers if ticker.strip()]
            
            if q_ticker not in article_tickers:
                continue
            
            key = url if url else f"{art.get('title','')}-{art.get('published_at','')}"
            
            if key and key not in existing_urls:
                existing_urls.add(key)
                new_articles_for_t.append(art)
        
        logger.info(f"{q_ticker}: found {len(articles)} articles, {len(new_articles_for_t)} new (filtered to articles mentioning {q_ticker})")
        to_append.extend(new_articles_for_t)
    
    if to_append:
        append_rows_to_csv(to_append)
    else:
        logger.info("No new articles found to append.")
    
    if requests_made:
        increment_request_count(requests_made)
# ---------- Helper to load CSV into Postgres ----------
def csv_to_postgres(conn_dsn: str, table_name: str = "articles"):
    """
    Bulk-load CSV into Postgres using simple INSERT ON CONFLICT DO NOTHING.
    This is convenience for iter1 -> iter2 migration.
    """
    import psycopg2
    ensure_csv_exists()
    conn = psycopg2.connect(conn_dsn)
    cur = conn.cursor()

    with open(CSV_PATH, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        inserted = 0
        for r in reader:
            if not r.get("url") and not r.get("title"):
                continue
            cur.execute(
                """
                INSERT INTO articles (url, title, description, published_at, sentiment, sentiment_score, prob_pos, prob_neg, prob_neu, source, tickers, raw_json)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (url) DO NOTHING
                """,
                (
                    r.get("url") or None,
                    r.get("title") or None,
                    r.get("description") or None,
                    r.get("published_at") or None,
                    r.get("sentiment") or None,
                    r.get("sentiment_score") or None,
                    r.get("prob_pos") or None,
                    r.get("prob_neg") or None,
                    r.get("prob_neu") or None,
                    r.get("source") or None,
                    (r.get("tickers") or None),
                    json.dumps(r),
                ),
            )
            inserted += 1
    conn.commit()
    cur.close()
    conn.close()
    logger.info(f"csv_to_postgres: attempted {inserted} inserts")
