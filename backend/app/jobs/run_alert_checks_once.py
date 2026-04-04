import logging

from app.services.alert_scheduler import run_alert_checks


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run_alert_checks()
    print("run_alert_checks_complete=true")


if __name__ == "__main__":
    main()
