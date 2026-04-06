import logging
import os
import traceback
from typing import List


logger = logging.getLogger("news_ingest_job")


def _has_env(name: str) -> bool:
    return bool((os.getenv(name) or "").strip())


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    ran_sources: List[str] = []

    if _has_env("MARKETAUX_API_TOKEN"):
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
