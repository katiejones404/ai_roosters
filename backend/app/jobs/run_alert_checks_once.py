import logging
import os
import sys


def _bootstrap_import_path() -> None:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    _bootstrap_import_path()
    from app.services.alert_scheduler import run_alert_checks

    run_alert_checks()
    print("run_alert_checks_complete=true")


if __name__ == "__main__":
    main()
