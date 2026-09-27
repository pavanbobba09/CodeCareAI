"""Expand clinical abbreviations (DM2, CKD, HFrEF, ...) before searching."""

import re
from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Abbreviation

_TOKEN = re.compile(r"[A-Za-z0-9]+")


def load_abbreviations(session: Session) -> dict[str, str]:
    rows = session.execute(select(Abbreviation.abbr, Abbreviation.expansion))
    return {abbr.upper(): expansion for abbr, expansion in rows}


def expand(text: str, abbreviations: Mapping[str, str]) -> tuple[str, bool]:
    """Replace whole-token abbreviations (case-insensitive). Returns (text, expanded?)."""
    expanded = False

    def swap(match: re.Match[str]) -> str:
        nonlocal expanded
        full = abbreviations.get(match.group(0).upper())
        if full is None:
            return match.group(0)
        expanded = True
        return full

    return _TOKEN.sub(swap, text), expanded
