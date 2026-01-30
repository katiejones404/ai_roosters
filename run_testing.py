"""Run all pytest tests under the ./Testing folder.

Usage:
  python run_testing.py
  python run_testing.py -q
  python run_testing.py Testing\\Articles -v

This script also ensures the backend package `app/` is importable by adding the
appropriate directory to PYTHONPATH/sys.path.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _ensure_import_paths() -> None:
    repo_root = Path(__file__).resolve().parent

    # Support both layouts:
    # - Local dev repo:   <repo>/Backend/app
    # - docker-compose:   /app/app  (Backend mounted directly at /app)
    candidates = [repo_root / "Backend", repo_root]

    for candidate in candidates:
        if (candidate / "app").exists():
            candidate_str = str(candidate)
            if candidate_str not in sys.path:
                sys.path.insert(0, candidate_str)

            existing = os.environ.get("PYTHONPATH", "")
            parts = [candidate_str, str(repo_root)]
            if existing:
                parts.append(existing)
            os.environ["PYTHONPATH"] = os.pathsep.join(parts)
            break


def main(argv: list[str]) -> int:
    _ensure_import_paths()

    # Runner flags (handled by this script, not forwarded to pytest)
    run_behave = True
    behave_only = False

    raw_args = argv[1:]
    pytest_args: list[str] = []

    for arg in raw_args:
        if arg == "--no-behave":
            run_behave = False
        elif arg == "--behave-only":
            behave_only = True
        else:
            pytest_args.append(arg)

    try:
        import pytest  # type: ignore
    except ModuleNotFoundError:
        print(
            "pytest is not installed in this Python environment.\n"
            "Install test deps (example):\n"
            "  python -m pip install -r Testing/User/test_requirements.txt\n",
            file=sys.stderr,
        )
        return 1

    exit_code = 0

    if not behave_only:
        if not pytest_args:
            pytest_args = ["Testing", "-v", "--tb=short"]
        exit_code = pytest.main(pytest_args)

    if run_behave:
        sentiment_behavioral_dir = Path("Testing") / "Sentiment" / "behavioral"
        if sentiment_behavioral_dir.exists():
            print("\n=== behave: Testing/Sentiment/behavioral ===")
            behave_rc = subprocess.call(
                [sys.executable, "-m", "behave", str(sentiment_behavioral_dir)]
            )
            exit_code = max(exit_code, behave_rc)
        else:
            print("\n(skipping behave: Testing/Sentiment/behavioral not found)")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
