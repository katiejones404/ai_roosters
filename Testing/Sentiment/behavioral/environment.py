from __future__ import annotations

import sys
from pathlib import Path

# Add Backend/ to sys.path at import-time so behave can import step modules safely.
_BACKEND_DIR = Path(__file__).resolve().parents[3] / "Backend"
if _BACKEND_DIR.exists():
    sys.path.insert(0, str(_BACKEND_DIR))


def before_all(context):
    # Path insertion already happened above.
    pass
