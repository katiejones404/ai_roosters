"""
One-shot job entry point that runs the full sentiment pipeline and exits.

Executes FinBERT article scoring, stock-level return processing, sentiment
aggregation, and GPT summary generation as sequential subprocess steps.
Intended to be executed by an Azure Container Apps Job on a cron schedule.
"""
import logging
import os
import subprocess
import sys


logger = logging.getLogger("sentiment_summary_job")


def _run_step(module_name: str) -> None:
    """Execute a Python module as a subprocess, inheriting the current environment with PYTHONPATH set."""
    logger.info("Running step: %s", module_name)
    env = os.environ.copy()
    app_root = "/app"
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{app_root}:{existing}" if existing else app_root
    subprocess.run([sys.executable, "-m", module_name], check=True, env=env)


def main() -> None:
    """Run all four sentiment pipeline steps in order: FinBERT scoring, returns, aggregation, GPT summaries."""
    logging.basicConfig(level=logging.INFO)
    logger.info("Sentiment summary job starting...")

    _run_step("app.services.sentiment.article_processing")
    _run_step("app.services.sentiment.stock_processing")
    _run_step("app.services.sentiment.aggregator")
    _run_step("app.services.sentiment.gpt_summary")

    logger.info("Sentiment summary job completed.")
    print("run_sentiment_summary_complete=true")


if __name__ == "__main__":
    main()
