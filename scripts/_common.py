"""Shared setup for scripts: run with the backend venv active (backend is pip-installed)."""

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
