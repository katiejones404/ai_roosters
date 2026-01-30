"""Shared test configuration.

Ensures the backend `app/` package (under `Backend/`) is importable from all
pytest runs, regardless of which Testing/* subfolder is executed.
"""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

# Support both layouts:
# - Local dev repo:   <repo>/Backend/app
# - docker-compose:   /app/app  (Backend is mounted directly at /app)
backend_dir_candidates = [
    REPO_ROOT / "Backend",
    REPO_ROOT,
]

for candidate in backend_dir_candidates:
    if (candidate / "app").exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

# Also allow absolute imports from repo root when tests expect it.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
