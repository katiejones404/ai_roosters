from __future__ import annotations

import sys
from pathlib import Path


# Ensure `Backend/` is on sys.path so imports like `from app...` work in unit tests.
_BACKEND_DIR = Path(__file__).resolve().parents[3] / "Backend"
if _BACKEND_DIR.exists():
    sys.path.insert(0, str(_BACKEND_DIR))
