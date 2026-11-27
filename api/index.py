"""Vercel serverless entrypoint exposing the FastAPI app."""

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"

for path_entry in (str(ROOT_DIR), str(SRC_DIR)):
    if path_entry not in sys.path:
        sys.path.insert(0, path_entry)

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

from src.lock_adapter import app  # noqa: E402, F401

