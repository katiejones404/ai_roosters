import logging
import os
import subprocess
import sys


logger = logging.getLogger("sentiment_summary_job")


def _run_step(module_name: str) -> None:
    logger.info("Running step: %s", module_name)
    env = os.environ.copy()
    app_root = "/app"
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{app_root}:{existing}" if existing else app_root
    subprocess.run([sys.executable, "-m", module_name], check=True, env=env)


def main() -> None:
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
