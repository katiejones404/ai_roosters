# services/alphavantage_ingest.py
# Commented out the ticker_sentiment_score/label variables, can be added back later if needed.
from __future__ import annotations
import os
import json
import csv
import logging
from datetime import datetime, date
from typing import List, Optional, Dict, Any
import requests
import time
from dotenv import load_dotenv
from pathlib import Path
from sqlalchemy import create_engine, MetaData, Table, text
from sqlalchemy.dialects.postgresql import insert

# Load .env from repo root
load_dotenv(dotenv_path=Path(__file__).resolve().parents[3] / ".env")

logger = logging.getLogger("alpha_ingest")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(handler)


# CONFIGURATION

API_KEY = os.getenv("ALPHAVANTAGE_API_KEY", "demo")
BASE_URL = "https://www.alphavantage.co/query"
CSV_PATH = os.getenv("AV_CSV_PATH", "../../data/article_api_data/ticker_sentiment.csv")
REQUESTS_LOG_PATH = os.getenv("AV_REQUESTS_LOG", "../../data/article_api_data/v2_requests_log.json")
REQUESTS_PER_DAY = int(os.getenv("AV_REQUESTS_PER_DAY", "22"))
DEFAULT_LIMIT = int(os.getenv("AV_DEFAULT_LIMIT", "100"))
RAW_DIR = os.getenv("AV_RAW_DIR", "../../data/article_api_data/v2_raw_responses")
os.makedirs(RAW_DIR, exist_ok=True)

# CSV columns - now storing TICKER-LEVEL sentiment, not article-level
CSV_FIELDS = [
    "article_url",
    "ticker",
    #"ticker_sentiment_score",
    #"ticker_sentiment_label",
    "relevance_score",
    "published_at",
    "article_title",
    "article_source",
    "fetched_at",
]

# REQUEST RATE LIMITING HELPERS----------------------------------------------

def _today_str() -> str:
    """Get today's date as ISO string"""
    return date.today().isoformat()

def load_requests_log() -> Dict[str, Any]:
    """Load the request counter log from disk"""
    if not os.path.exists(REQUESTS_LOG_PATH):
        return {"date": _today_str(), "count": 0}
    try:
        with open(REQUESTS_LOG_PATH, "r") as f:
            data = json.load(f)
    except Exception:
        return {"date": _today_str(), "count": 0}
    
    # Reset counter if it's a new day
    if data.get("date") != _today_str():
        return {"date": _today_str(), "count": 0}
    return data

def save_requests_log(log: Dict[str, Any]) -> None:
    """Save the request counter log to disk"""
    os.makedirs(os.path.dirname(REQUESTS_LOG_PATH) or ".", exist_ok=True)
    with open(REQUESTS_LOG_PATH, "w") as f:
        json.dump(log, f)

def increment_request_count(n: int = 1) -> None:
    """Increment the daily request counter"""
    log = load_requests_log()
    log["count"] = int(log.get("count", 0)) + n
    log["date"] = _today_str()
    save_requests_log(log)

def remaining_requests() -> int:
    """Get number of remaining API requests for today"""
    log = load_requests_log()
    return max(0, REQUESTS_PER_DAY - int(log.get("count", 0)))

#
# CSV STORAGE HELPERS- ----------------------------------------
def ensure_csv_exists():
    """Create CSV file with headers if it doesn't exist"""
    os.makedirs(os.path.dirname(CSV_PATH) or ".", exist_ok=True)
    if not os.path.exists(CSV_PATH):
        with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()

def load_existing_article_ticker_pairs() -> set:
    """
    Load existing (article_url, ticker) pairs from CSV to avoid duplicates.
    Returns a set of tuples: {(url, ticker), ...}
    """
    ensure_csv_exists()
    pairs = set()
    try:
        with open(CSV_PATH, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                url = r.get("article_url", "").strip()
                ticker = r.get("ticker", "").strip()
                if url and ticker:
                    pairs.add((url, ticker))
    except FileNotFoundError:
        return set()
    return pairs

def append_ticker_sentiments_to_csv(rows: List[Dict[str, Any]]):
    """Append ticker sentiment rows to CSV"""
    ensure_csv_exists()
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        for r in rows:
            # Ensure all fields are present
            out = {k: (r.get(k) if r.get(k) is not None else "") for k in CSV_FIELDS}
            writer.writerow(out)
    logger.info(f"Appended {len(rows)} ticker sentiment rows to {CSV_PATH}")

# ALPHAVANTAGE API CALLS---------------------

def call_alphavantage_news(
    tickers: Optional[str] = None,
    topics: Optional[str] = None,
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
    limit: int = DEFAULT_LIMIT,
    max_retries: int = 3
) -> Dict[str, Any]:
    """
    Call AlphaVantage NEWS_SENTIMENT API with retry logic.
    
    Args:
        tickers: Comma-separated ticker symbols
        topics: Comma-separated topics
        time_from: Start time (format: YYYYMMDDTHHMM)
        time_to: End time (format: YYYYMMDDTHHMM)
        limit: Max articles to return
        max_retries: Number of retry attempts
        
    Returns:
        Parsed JSON response from API
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
    backoff = 1.1  # Initial backoff in seconds
    
    while attempt <= max_retries:
        attempt += 1
        try:
            resp = requests.get(BASE_URL, params=params, timeout=30)
        except Exception as e:
            logger.exception(f"Network error on API call (attempt {attempt}): {e!r}")
            if attempt > max_retries:
                raise
            time.sleep(backoff)
            backoff *= 2
            continue

        # Parse JSON response
        try:
            parsed = resp.json()
        except Exception:
            parsed = {"_raw_text": resp.text}

        # Save raw response for debugging
        safe_name = (tickers or "global").replace(",", "_").replace(":", "_").replace(" ", "_")
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        out_path = Path(RAW_DIR) / f"{safe_name}_{ts}_attempt{attempt}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(parsed, f, indent=2)
        logger.info(f"Saved raw API response to {out_path}")

        # Check for API rate limit or error messages
        if isinstance(parsed, dict) and any(k in parsed for k in ("Information", "Note", "Error Message")):
            msg_key = next(k for k in ("Information", "Note", "Error Message") if k in parsed)
            logger.warning(f"AlphaVantage returned {msg_key}: {parsed[msg_key]}")
            
            if attempt > max_retries:
                logger.error("Max retries exhausted")
                return parsed
            
            time.sleep(backoff)
            backoff *= 2
            continue

        # Success - wait politely before returning (API recommends ~1 req/sec)
        time.sleep(1.1)
        return parsed

    return parsed

# DATA EXTRACTION AND TRANSFORMATION-----------------------------------------

def extract_ticker_sentiments_from_response(resp_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract TICKER-LEVEL sentiment data from AlphaVantage response.
    
    Each article can mention multiple tickers, so we create one row per ticker per article.
    
    Returns:
        List of dicts with ticker sentiment data, one row per (article, ticker) pair
    """
    out = []
    
    # Find the article feed in the response
    candidates = []
    for key in ("feed", "items", "data", "articles", "news"):
        if isinstance(resp_json.get(key), list):
            candidates = resp_json.get(key)
            break
    
    # Fallback: find first list value
    if not candidates and isinstance(resp_json, dict):
        for v in resp_json.values():
            if isinstance(v, list):
                candidates = v
                break
    
    # Process each article
    for article in candidates:
        # Extract article-level metadata
        article_url = article.get("url") or article.get("link") or ""
        article_title = article.get("title") or article.get("headline") or ""
        article_source = article.get("source") or article.get("publisher") or ""
        article_description = article.get("summary") or article.get("description") or ""

        # Parse published time
        pub = article.get("time_published") or article.get("published_at") or article.get("published") or ""
        published_at = ""
        
        if pub:
            try:
                # AlphaVantage format: YYYYMMDDTHHMMSS
                if len(pub) == 15 and 'T' in pub:
                    dt = datetime.strptime(pub, "%Y%m%dT%H%M%S")
                else:
                    dt = datetime.fromisoformat(pub)
                published_at = dt.isoformat()
            except Exception:
                published_at = str(pub)
        
        # Extract ticker-specific sentiment
        ticker_sentiment_list = article.get("ticker_sentiment") or []
        
        if not isinstance(ticker_sentiment_list, list):
            continue
        
        # Create one row per ticker mentioned in the article- ticker_sentiment contains multiple tickers and their data 
        for ticker_data in ticker_sentiment_list:
            ticker = ticker_data.get("ticker")
            if not ticker:
                continue
            
            # Extract ticker-specific sentiment scores
            #ticker_sentiment_score = ticker_data.get("ticker_sentiment_score")
            #ticker_sentiment_label = ticker_data.get("ticker_sentiment_label") or ""
            relevance_score = ticker_data.get("relevance_score")
            
            # Convert scores to float
            '''
            try:
                ticker_sentiment_score = float(ticker_sentiment_score) if ticker_sentiment_score is not None else None
            except (ValueError, TypeError):
                ticker_sentiment_score = None
            '''
            try:
                relevance_score = float(relevance_score) if relevance_score is not None else None
            except (ValueError, TypeError):
                relevance_score = None
            
            # Create a row for this (article, ticker) pair
            out.append({
                "article_url": article_url,
                "ticker": ticker.upper(),
                #"ticker_sentiment_score": ticker_sentiment_score,
                #"ticker_sentiment_label": ticker_sentiment_label.lower() if ticker_sentiment_label else "",
                "relevance_score": relevance_score,
                "published_at": published_at,
                "article_title": article_title,
                "article_source": article_source,
                "article_description": article_description,
                "fetched_at": datetime.utcnow().isoformat(),
            })
    
    return out

# DATABASE STORAGE -----------------------------------------------

class AlphaVantageIngestor:
    """
    Ingests ticker-level sentiment data from AlphaVantage into PostgreSQL.
    Pattern follows PriceIngestor from prices_ingest.py
    """
    
    def __init__(self, db_url: Optional[str] = None):
        """Initialize database connection and reflect tables"""
        if db_url is None:
            db_url = os.getenv(
                "DATABASE_URL",
                "postgresql://stock_user:stock_pass@postgres:5432/stock_db"
            )
        
        logger.info(f"Connecting to database...")
        self.engine = create_engine(db_url)
        self.metadata = MetaData()
        
        # Reflect the articles table (for basic article metadata)
        logger.info("Reflecting database tables...")
        self.metadata.reflect(self.engine, only=["articles", "article_ticker_sentiment"])
        
        # Get table references
        if "articles" not in self.metadata.tables:
            raise RuntimeError("Table 'articles' does not exist. Run init SQL first.")
        if "article_ticker_sentiment" not in self.metadata.tables:
            raise RuntimeError("Table 'article_ticker_sentiment' does not exist. Run init SQL first.")
        
        self.articles_table: Table = self.metadata.tables["articles"]
        self.ticker_sentiment_table: Table = self.metadata.tables["article_ticker_sentiment"]
        
        logger.info("Successfully connected to database and reflected tables.")
    
    def get_existing_article_ticker_pairs(self) -> set:
        """
        Get existing (article_url, ticker) pairs from database.
        Returns set of tuples to check for duplicates.
        """
        try:
            with self.engine.connect() as conn:
                query = text("""
                    SELECT article_url, ticker 
                    FROM article_ticker_sentiment
                """)
                result = conn.execute(query)
                return {(row[0], row[1]) for row in result}
        except Exception as e:
            logger.error(f"Error fetching existing pairs: {e}")
            return set()
    
    def store_article_metadata(self, ticker_sentiments: List[Dict[str, Any]]) -> None:
        """
        Store basic article metadata in the articles table.
        This ensures foreign key references work.
        
        Uses ON CONFLICT DO NOTHING since we only need basic metadata.
        """
        if not ticker_sentiments:
            return
        
        # Extract unique articles
        articles_map = {}
        for ts in ticker_sentiments:
            url = ts.get("article_url")
            if url and url not in articles_map:
                articles_map[url] = {
                    "url": url,
                    "title": ts.get("article_title"),
                    "source": ts.get("article_source"),
                    "description": ts.get("article_description"),
                    "published_at": ts.get("published_at"),
                    # FinBERT will fill in sentiment fields later if needed
                }
        
        articles = list(articles_map.values())
        
        try:
            with self.engine.begin() as conn:
                stmt = insert(self.articles_table).values(articles)
                # Don't overwrite existing articles
                stmt = stmt.on_conflict_do_nothing(index_elements=["url"])
                conn.execute(stmt)
            
            logger.info(f"Stored metadata for {len(articles)} unique articles")
        except Exception as e:
            logger.error(f"Error storing article metadata: {e}")
            raise
    
    def store_ticker_sentiments(
        self, 
        ticker_sentiments: List[Dict[str, Any]], 
        update_existing: bool = False
    ) -> None:
        """
        Store ticker-level sentiment data in article_ticker_sentiment table.
        
        Args:
            ticker_sentiments: List of ticker sentiment records
            update_existing: If True, update existing records. If False, skip duplicates.
        """
        if not ticker_sentiments:
            logger.warning("No ticker sentiment data to store")
            return
        
        try:
            # First, ensure article metadata exists
            self.store_article_metadata(ticker_sentiments)
            
            # Prepare records for insertion
            records = []
            for ts in ticker_sentiments:
                records.append({
                    "article_url": ts.get("article_url"),
                    "ticker": ts.get("ticker"),
                    #"ticker_sentiment_score": ts.get("ticker_sentiment_score"),
                    #"ticker_sentiment_label": ts.get("ticker_sentiment_label"),
                    "relevance_score": ts.get("relevance_score"),
                    "published_at": ts.get("published_at"),
                })
            
            # Insert in batches
            total_records = len(records)
            batch_size = 100
            records_processed = 0
            
            for i in range(0, total_records, batch_size):
                batch = records[i : i + batch_size]
                
                with self.engine.begin() as conn:
                    stmt = insert(self.ticker_sentiment_table).values(batch)
                    
                    if update_existing:
                        # Upsert on (article_url, ticker)
                        stmt = stmt.on_conflict_do_update(
                            index_elements=["article_url", "ticker"],
                            set_={
                                #"ticker_sentiment_score": stmt.excluded.ticker_sentiment_score,
                                #"ticker_sentiment_label": stmt.excluded.ticker_sentiment_label,
                                "relevance_score": stmt.excluded.relevance_score,
                                "published_at": stmt.excluded.published_at,
                            },
                        )
                    else:
                        # Skip if already exists
                        stmt = stmt.on_conflict_do_nothing(
                            index_elements=["article_url", "ticker"]
                        )
                    
                    conn.execute(stmt)
                    records_processed += len(batch)
                    logger.info(f"Processed {records_processed}/{total_records} ticker sentiment records")
            
            logger.info(f"Successfully stored {total_records} ticker sentiment records")
            
        except Exception as e:
            logger.error(f"Error storing ticker sentiments: {e}")
            raise
    
    def ingest_for_tickers(
        self,
        tickers: List[str],
        topics: Optional[List[str]] = None,
        time_from: Optional[str] = None,
        time_to: Optional[str] = None,
        limit: int = DEFAULT_LIMIT,
        update_existing: bool = False,
        save_to_csv: bool = True,
    ) -> None:
        """
        Main ingestion method - fetch and store ticker sentiment data.
        
        Args:
            tickers: List of ticker symbols to fetch news for
            topics: Optional topic filters
            time_from: Start date (format: YYYYMMDDTHHMM)
            time_to: End date (format: YYYYMMDDTHHMM)
            limit: Max articles per API call
            update_existing: Whether to update existing DB records
            save_to_csv: Whether to also save to CSV
        """
        remaining = remaining_requests()
        if remaining <= 0:
            logger.warning("No remaining API requests for today. Exiting.")
            return
        
        # Load existing data to avoid duplicates
        existing_pairs = self.get_existing_article_ticker_pairs()
        if save_to_csv:
            existing_pairs.update(load_existing_article_ticker_pairs())
        
        all_ticker_sentiments = []
        requests_made = 0
        
        # Fetch data for each ticker
        for ticker in tickers:
            if remaining <= 0:
                logger.warning("Reached daily API quota")
                break
            
            ticker = ticker.strip().upper()
            logger.info(f"Fetching news for {ticker}...")
            
            # Call AlphaVantage API
            resp = call_alphavantage_news(
                tickers=ticker,
                topics=",".join(topics) if topics else None,
                time_from=time_from,
                time_to=time_to,
                limit=limit
            )
            
            # Check for API errors
            if isinstance(resp, dict) and any(k in resp for k in ("Information", "Note", "Error Message")):
                logger.warning(f"API returned error for {ticker}, stopping")
                break
            
            requests_made += 1
            remaining -= 1
            
            # Extract ticker sentiments from response
            ticker_sentiments = extract_ticker_sentiments_from_response(resp)
            
            # Filter out duplicates and only keep sentiments for the requested ticker
            new_sentiments = []
            for ts in ticker_sentiments:
                # Only include if this ticker is mentioned AND it's the one we searched for
                if ts.get("ticker") == ticker:
                    pair = (ts.get("article_url"), ts.get("ticker"))
                    if pair not in existing_pairs:
                        existing_pairs.add(pair)
                        new_sentiments.append(ts)
            
            logger.info(f"{ticker}: found {len(ticker_sentiments)} total ticker mentions, {len(new_sentiments)} new")
            all_ticker_sentiments.extend(new_sentiments)
        
        # Store results
        if all_ticker_sentiments:
            # Save to database
            self.store_ticker_sentiments(all_ticker_sentiments, update_existing=update_existing)
            
            # Save to CSV
            if save_to_csv:
                append_ticker_sentiments_to_csv(all_ticker_sentiments)
        else:
            logger.info("No new ticker sentiments to store")
        
        # Update request counter
        if requests_made:
            increment_request_count(requests_made)
            logger.info(f"Used {requests_made} API requests. {remaining_requests()} remaining today.")


# CONVENIENCE FUNCTION FOR MAIN.PY---------------------------

def ingest_alphavantage_news(
    db_url: str,
    tickers: List[str],
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
    limit: int = 100,
) -> None:
    """    
    Example usage:
        ingest_alphavantage_news(
            db_url="postgresql://user:pass@host:port/db",
            tickers=["BP", "RELIANCE.NS"],
            time_from="20250101T0000",
            time_to="20251231T2359"
        )
    """
    ingestor = AlphaVantageIngestor(db_url)
    ingestor.ingest_for_tickers(
        tickers=tickers,
        time_from=time_from,
        time_to=time_to,
        limit=limit,
        update_existing=False,
        save_to_csv=True,
    )


# CLI USAGE ----------------------

if __name__ == "__main__":
    # Example CLI usage
    import time
    
    ingestor = AlphaVantageIngestor()
    ingestor.ingest_for_tickers(
        tickers=["AAPL", "MSFT"],
        time_from="20250101T0000",
        time_to="20251231T2359",
        limit=100,
        update_existing=False,
        save_to_csv=True,
    )
    logger.info("CLI ingestion complete")