# Testing/unit/conftest.py
from __future__ import annotations
import sys
from pathlib import Path

# THIS FILE RUNS BEFORE ANY TEST IMPORTS. It must be portable.
THIS_DIR = Path(__file__).resolve().parent      # .../~/Testing
REPO_ROOT = THIS_DIR.parent                     

# Path to the folder that contains `app` or `backend` packages
BACKEND_DIR = REPO_ROOT / "backend"

# Make repo root importable (so `import backend...` works)
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Also add back end dir so `import app...` works just in cas
if BACKEND_DIR.exists() and str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# debug line
# print("conftest inserted:", sys.path[0], sys.path[1] if len(sys.path) > 1 else None)
