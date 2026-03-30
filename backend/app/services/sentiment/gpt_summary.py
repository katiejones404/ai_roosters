from __future__ import annotations

import os
import sys
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests
from sqlalchemy import MetaData, Table, create_engine, select
from sqlalchemy.dialects.postgresql import insert

# Optional: project root on path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger("stock_news_summary")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Keep this aligned with the stocks shown on the website
TARGET_TICKERS = [
    "KSS", "ALK", "NVS", "AXP", "FCX",
    "CSX", "DAL", "NTAP", "AMZN", "AEO",
    "MRK", "NVDA", "COP", "BHP", "EA",
]


# ---------------------------
# DB helpers
# ---------------------------

def build_db_url() -> str:
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return db_url

    db_user = os.getenv("PG_USER", "stock_user")
    db_password = os.getenv("PG_PASS", "stock_pass")
    db_host = os.getenv("PG_HOST", "postgres")
    db_port = os.getenv("PG_PORT", "5432")
    db_name = os.getenv("PG_DB", "stock_db")
    return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"


# ---------------------------
# LLM helpers
# ---------------------------

def get_llm_base_url() -> str:
    return (
        os.getenv("NEWS_SUMMARY_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or "https://api.openai.com/v1"
    ).rstrip("/")


def get_llm_api_key() -> Optional[str]:
    key = (
        os.getenv("NEWS_SUMMARY_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or ""
    ).strip()
    return key or None


def get_llm_model() -> str:
    return (os.getenv("NEWS_SUMMARY_MODEL") or "gpt-4.1-mini").strip()


def get_llm_timeout() -> int:
    return int(os.getenv("NEWS_SUMMARY_TIMEOUT", "120"))


def get_llm_temperature() -> float:
    return float(os.getenv("NEWS_SUMMARY_TEMPERATURE", "0.2"))


# ---------------------------
# Utility helpers
# ---------------------------

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_datetime_utc(raw: Any) -> Optional[datetime]:
    if raw is None:
        return None

    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw.astimezone(timezone.utc)

    s = str(raw).strip()
    if not s:
        return None

    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt
    except Exception:
        return None


def clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def dedupe_keep_order(values: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for v in values:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def normalize_summary_text(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return "No recent stock-specific articles were found for this window."

    lines = [line.strip(" -*\t") for line in text.splitlines() if line.strip()]
    text = " ".join(lines)
    text = " ".join(text.split())
    return text


def format_article_for_prompt(idx: int, article: Dict[str, Any]) -> str:
    published_at = article.get("published_at")
    if isinstance(published_at, datetime):
        date_str = published_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    else:
        date_str = "unknown date"

    title = article.get("title") or "Untitled"
    source = article.get("source") or "Unknown source"
    description = article.get("description") or ""
    snippet = article.get("snippet") or ""
    relevance_score = article.get("relevance_score")

    extra = description if description else snippet
    extra = extra[:400].strip() if extra else ""
    score_str = f"{relevance_score}" if relevance_score is not None else "N/A"

    parts = [
        f"Article {idx}:",
        f"Date: {date_str}",
        f"Source: {source}",
        f"Title: {title}",
        f"Relevance Score: {score_str}",
    ]
    if extra:
        parts.append(f"Context: {extra}")

    return "\n".join(parts)


# ---------------------------
# Core summarizer
# ---------------------------

class StockNewsSummaryGenerator:
    """
    Reads isolated recent articles from:
      - stock_news_articles

    Writes summaries to:
      - stock_news_summaries

    Does NOT use:
      - articles
      - article_ticker_mentions
      - article_ticker_sentiment
      - sentiment_snapshots
    """

    def __init__(self, db_url: Optional[str] = None):
        if db_url is None:
            db_url = build_db_url()

        self.base_url = get_llm_base_url()
        self.api_key = get_llm_api_key()
        self.model = get_llm_model()
        self.timeout = get_llm_timeout()
        self.temperature = get_llm_temperature()

        logger.info(f"Connecting to database at {db_url} ...")
        self.engine = create_engine(db_url)
        self.metadata = MetaData()

        logger.info("Reflecting required tables...")
        self.metadata.reflect(self.engine, only=["stock_news_articles", "stock_news_summaries"])

        if "stock_news_articles" not in self.metadata.tables:
            raise RuntimeError("Table 'stock_news_articles' does not exist in the database.")
        if "stock_news_summaries" not in self.metadata.tables:
            raise RuntimeError("Table 'stock_news_summaries' does not exist in the database.")

        self.stock_news_articles: Table = self.metadata.tables["stock_news_articles"]
        self.stock_news_summaries: Table = self.metadata.tables["stock_news_summaries"]

        self.article_cols = set(self.stock_news_articles.c.keys())
        self.summary_cols = set(self.stock_news_summaries.c.keys())

        logger.info(f"Reflected 'stock_news_articles'. columns={sorted(self.article_cols)}")
        logger.info(f"Reflected 'stock_news_summaries'. columns={sorted(self.summary_cols)}")

        required_article_cols = {"ticker", "published_at"}
        missing_article_cols = [c for c in required_article_cols if c not in self.article_cols]
        if missing_article_cols:
            raise RuntimeError(
                f"'stock_news_articles' missing required columns: {missing_article_cols}"
            )

        required_summary_cols = {"ticker", "window_days", "summary_text"}
        missing_summary_cols = [c for c in required_summary_cols if c not in self.summary_cols]
        if missing_summary_cols:
            raise RuntimeError(
                f"'stock_news_summaries' missing required columns: {missing_summary_cols}"
            )

    # ---------------------------
    # Ticker resolution
    # ---------------------------

    def resolve_target_tickers(self) -> List[str]:
        env_symbols = (os.getenv("NEWS_SUMMARY_TICKERS") or "").strip()
        if env_symbols:
            tickers = [x.strip().upper() for x in env_symbols.split(",") if x.strip()]
            tickers = dedupe_keep_order(tickers)
            logger.info(f"Using NEWS_SUMMARY_TICKERS override with {len(tickers)} ticker(s).")
            return tickers

        logger.info(f"Using hardcoded website ticker universe with {len(TARGET_TICKERS)} ticker(s).")
        return TARGET_TICKERS.copy()

    def resolve_windows(self) -> List[int]:
        raw = (os.getenv("NEWS_SUMMARY_WINDOWS") or "7").strip()
        windows: List[int] = []
        for x in raw.split(","):
            x = x.strip()
            if not x:
                continue
            try:
                value = int(x)
                if value > 0:
                    windows.append(value)
            except Exception:
                continue

        windows = dedupe_keep_order([str(w) for w in windows])
        return [int(w) for w in windows] if windows else [7]

    # ---------------------------
    # Article loading
    # ---------------------------

    def load_recent_articles(
        self,
        ticker: str,
        window_days: int,
        max_articles: int,
    ) -> List[Dict[str, Any]]:
        cutoff = utc_now() - timedelta(days=window_days)

        cols = [self.stock_news_articles.c.ticker, self.stock_news_articles.c.published_at]
        optional_cols = [
            "url",
            "title",
            "source",
            "description",
            "snippet",
            "image_url",
            "language",
            "relevance_score",
        ]
        for col in optional_cols:
            if col in self.article_cols:
                cols.append(self.stock_news_articles.c[col])

        stmt = (
            select(*cols)
            .where(
                self.stock_news_articles.c.ticker == ticker,
                self.stock_news_articles.c.published_at.is_not(None),
                self.stock_news_articles.c.published_at >= cutoff,
            )
            .order_by(self.stock_news_articles.c.published_at.desc())
            .limit(max_articles)
        )

        with self.engine.begin() as conn:
            rows = conn.execute(stmt).fetchall()

        articles: List[Dict[str, Any]] = []
        for row in rows:
            articles.append(dict(row._mapping))

        return articles

    # ---------------------------
    # Prompting + model call
    # ---------------------------

    def build_prompts(
        self,
        ticker: str,
        window_days: int,
        articles: List[Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        system_prompt = (
            "You are a financial news summarizer. "
            "Write one concise paragraph summarizing recent stock-specific news based only on the provided articles. "
            "Do not mention sentiment scores. "
            "Do not give investment advice. "
            "Do not invent facts that are not in the article list. "
            "If coverage is sparse, say that coverage is limited."
        )

        article_blocks = [format_article_for_prompt(i + 1, a) for i, a in enumerate(articles)]
        article_text = "\n\n".join(article_blocks)

        user_prompt = (
            f"Ticker: {ticker}\n"
            f"Window: last {window_days} days\n\n"
            "Write one plain-text paragraph of about 4 to 6 sentences that highlights the most important recent "
            "events, business updates, products, earnings, regulation, partnerships, demand signals, or other themes "
            "present in the article set.\n\n"
            "Focus on what happened recently and why it matters for this company. "
            "Keep the tone factual and concise.\n\n"
            "Articles:\n"
            f"{article_text}"
        )

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def call_chat_model(self, messages: List[Dict[str, str]]) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        if resp.status_code >= 400:
            raise RuntimeError(f"LLM request failed ({resp.status_code}): {resp.text[:500]}")

        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("LLM response did not contain any choices.")

        message = choices[0].get("message") or {}
        content = message.get("content")

        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, dict):
                    text_value = item.get("text")
                    if text_value:
                        parts.append(str(text_value))
            return "\n".join(parts).strip()

        raise RuntimeError("LLM response content was not a supported format.")

    # ---------------------------
    # DB write
    # ---------------------------

    def upsert_summary(
        self,
        ticker: str,
        window_days: int,
        summary_text: str,
        article_count: int,
        latest_article_at: Optional[datetime],
    ) -> int:
        record = {
            "ticker": ticker,
            "window_days": window_days,
            "summary_text": summary_text,
            "article_count": article_count,
            "latest_article_at": latest_article_at,
            "generated_at": utc_now(),
            "model": self.model,
        }

        record = {k: v for k, v in record.items() if k in self.summary_cols}

        with self.engine.begin() as conn:
            stmt = insert(self.stock_news_summaries).values(record)
            stmt = stmt.on_conflict_do_update(
                index_elements=["ticker", "window_days"],
                set_={
                    "summary_text": stmt.excluded.summary_text,
                    "article_count": stmt.excluded.article_count,
                    "latest_article_at": stmt.excluded.latest_article_at,
                    "generated_at": stmt.excluded.generated_at,
                    "model": stmt.excluded.model,
                },
            )
            result = conn.execute(stmt)
            return result.rowcount or 0

    # ---------------------------
    # Main summary flow
    # ---------------------------

    def summarize_one(
        self,
        ticker: str,
        window_days: int,
        max_articles: int,
    ) -> None:
        articles = self.load_recent_articles(
            ticker=ticker,
            window_days=window_days,
            max_articles=max_articles,
        )

        article_count = len(articles)
        latest_article_at = articles[0]["published_at"] if articles else None

        if not articles:
            summary_text = "No recent stock-specific articles were found for this window."
            written = self.upsert_summary(
                ticker=ticker,
                window_days=window_days,
                summary_text=summary_text,
                article_count=0,
                latest_article_at=None,
            )
            logger.info(
                f"[STOCK-NEWS-SUMMARY] ticker={ticker} window_days={window_days} "
                f"articles=0 upserted={written}"
            )
            return

        messages = self.build_prompts(
            ticker=ticker,
            window_days=window_days,
            articles=articles,
        )
        raw_summary = self.call_chat_model(messages)
        summary_text = normalize_summary_text(raw_summary)

        written = self.upsert_summary(
            ticker=ticker,
            window_days=window_days,
            summary_text=summary_text,
            article_count=article_count,
            latest_article_at=latest_article_at,
        )

        logger.info(
            f"[STOCK-NEWS-SUMMARY] ticker={ticker} window_days={window_days} "
            f"articles={article_count} upserted={written}"
        )

    def run(
        self,
        tickers: Optional[List[str]] = None,
        windows: Optional[List[int]] = None,
        max_articles_per_summary: int = 8,
    ) -> None:
        if tickers is None:
            tickers = self.resolve_target_tickers()
        if windows is None:
            windows = self.resolve_windows()

        tickers = dedupe_keep_order([t.strip().upper() for t in tickers if t and t.strip()])
        windows = [int(w) for w in windows if int(w) > 0]

        if not tickers:
            logger.warning("No tickers provided. Nothing to summarize.")
            return
        if not windows:
            logger.warning("No windows provided. Nothing to summarize.")
            return

        logger.info(
            f"STOCK-NEWS-SUMMARY start tickers={len(tickers)} "
            f"windows={windows} max_articles_per_summary={max_articles_per_summary} "
            f"model={self.model}"
        )

        completed = 0
        failed = 0

        for ticker in tickers:
            for window_days in windows:
                try:
                    self.summarize_one(
                        ticker=ticker,
                        window_days=window_days,
                        max_articles=max_articles_per_summary,
                    )
                    completed += 1
                except Exception as exc:
                    failed += 1
                    logger.exception(
                        f"[STOCK-NEWS-SUMMARY] FAILED ticker={ticker} window_days={window_days}: {exc}"
                    )

        logger.info(
            f"STOCK-NEWS-SUMMARY DONE completed={completed} failed={failed}"
        )


if __name__ == "__main__":
    gen = StockNewsSummaryGenerator()

    max_articles_per_summary = int(os.getenv("NEWS_SUMMARY_ARTICLE_LIMIT", "8"))

    gen.run(
        tickers=None,   # uses NEWS_SUMMARY_TICKERS or hardcoded TARGET_TICKERS
        windows=None,   # uses NEWS_SUMMARY_WINDOWS or default [7]
        max_articles_per_summary=max_articles_per_summary,
    )