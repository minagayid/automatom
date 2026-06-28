"""Automatom sample workflow filetree.

This filetree is also the README-backed API surface for contributors,
so keep the descriptions precise about what each entry contains.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
f"Automatom workflow API tree at {ROOT}\n"

PYTHON_SOURCES = sorted(
    [p for p in ROOT.glob("**/*.py") if p.name != "__pycache__"],
)

CONTRIB_GUIDE_ROUTES = [
    "app/schemas.py: workflow schema + pydantic models",
    "app/services/records.py: DB read/write over SQLite.",
    "app/engine.py: scheduler + step runner + extension registry.",
    "app/main.py: FastAPI server scaffolding.",
]
"Open-ended API categories: list supported intent types, trigger types, and step types.",
