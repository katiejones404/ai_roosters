"""
One-shot job entry point that ingests news from all configured sources and exits.

Runs Marketaux, NewsAPI, AlphaVantage, and Guardian in sequence. Each source is
skipped gracefully if its API key environment variable is not set.
Intended to be executed by an Azure Container Apps Job on a cron schedule.
"""
import logging
import os
import sys
import traceback
from typing import List


logger = logging.getLogger("news_ingest_job")


def _bootstrap_import_path() -> None:
    # When this file is executed as `python app/jobs/run_news_ingest_once.py`,
    # ensure repo root (/app in container) is on sys.path so `import app...` works.
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


def _has_env(name: str) -> bool:
    """Return True if the named environment variable is set to a non-empty value."""
    return bool((os.getenv(name) or "").strip())


def main() -> None:
    """Run news ingestion for each source whose API key is present in the environment."""
    logging.basicConfig(level=logging.INFO)
    _bootstrap_import_path()

    ran_sources: List[str] = []
    attempted_sources = 0

    if _has_env("MARKETAUX_API_TOKEN"):
        attempted_sources += 1
        try:
            from app.services.ingesting_pipelines.daily_news_ingest import (
                run_daily_news_ingest_from_env,
            )

            run_daily_news_ingest_from_env()
            ran_sources.append("marketaux")
        except Exception as exc:
            logger.exception("Marketaux ingest failed: %s", exc)
    else:
        logger.warning("Skipping Marketaux ingest: MARKETAUX_API_TOKEN is not set.")

    if _has_env("NEWSAPI_API_KEY"):
        attempted_sources += 1
        try:
            from app.services.ingesting_pipelines.newsapi_ingest import (
                run_newsapi_ingest_from_env,
            )

            run_newsapi_ingest_from_env()
            ran_sources.append("newsapi")
        except Exception as exc:
            logger.exception("NewsAPI ingest failed: %s", exc)
    else:
        logger.warning("Skipping NewsAPI ingest: NEWSAPI_API_KEY is not set.")

    if _has_env("ALPHAVANTAGE_API_KEY"):
        attempted_sources += 1
        try:
            from app.services.ingesting_pipelines.alphavantage_ingest import (
                run_alphavantage_ingest_from_env,
            )

            run_alphavantage_ingest_from_env()
            ran_sources.append("alphavantage")
        except Exception as exc:
            logger.exception("AlphaVantage ingest failed: %s", exc)
    else:
        logger.warning("Skipping AlphaVantage ingest: ALPHAVANTAGE_API_KEY is not set.")

    if _has_env("GUARDIAN_API_KEY"):
        attempted_sources += 1
        try:
            from app.services.ingesting_pipelines.guardian_ingest import (
                run_guardian_ingest_from_env,
            )

            run_guardian_ingest_from_env()
            ran_sources.append("guardian")
        except Exception as exc:
            logger.exception("Guardian ingest failed: %s", exc)
    else:
        logger.warning("Skipping Guardian ingest: GUARDIAN_API_KEY is not set.")

    if not ran_sources:
        logger.warning("No news ingestors ran. Set at least one news API key.")
        if attempted_sources > 0:
            raise RuntimeError(
                "No news ingestors completed successfully; check module import/runtime errors."
            )
    else:
        logger.info("News ingest job completed. Sources run: %s", ", ".join(ran_sources))


if __name__ == "__main__":
    try:
        main()
        print("run_news_ingest_complete=true", flush=True)
    except BaseException as exc:
        print(f"run_news_ingest_failed={exc!r}", flush=True)
        traceback.print_exc()
        raise
