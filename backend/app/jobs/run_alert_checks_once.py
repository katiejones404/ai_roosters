"""
One-shot job entry point that runs a single pass of all active price alert checks and exits.

Intended to be executed by an Azure Container Apps Job on a cron schedule.
"""
import logging
import os
import sys


def _bootstrap_import_path() -> None:
    """Add the project root to sys.path so that 'import app...' resolves correctly when run directly."""
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


def main() -> None:
    """Bootstrap the import path and run one pass of active alert checks."""
    logging.basicConfig(level=logging.INFO)
    _bootstrap_import_path()
    from app.services.alert_scheduler import run_alert_checks

    run_alert_checks()
    print("run_alert_checks_complete=true")


if __name__ == "__main__":
    main()
