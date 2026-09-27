"""Load and check gold notes (DESIGN.md §5.4)."""

import hashlib
import json
import re
from collections.abc import Callable
from datetime import date
from pathlib import Path

from app.models.eval import GoldNote

GOLD_DIR = Path(__file__).resolve().parents[1] / "data" / "gold_notes"
RULE_ID = re.compile(r"^R([1-9]|1[0-4])$")

# (code, visit_date) -> (exists in the code set for that date, billable)
CodeCheck = Callable[[str, date], tuple[bool, bool]]


def load_gold(directory: Path = GOLD_DIR) -> list[GoldNote]:
    return [
        GoldNote.model_validate(json.loads(p.read_text()))
        for p in sorted(directory.glob("n*.json"))
    ]


def gold_hash(note: GoldNote) -> str:
    """Content hash of a gold note; a run stores one per note so changes are detected."""
    canonical = json.dumps(note.model_dump(mode="json"), sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def changed_notes(hashes: dict[str, str], golds: list[GoldNote]) -> list[str]:
    """Note ids whose gold note is gone or no longer matches the stored hash."""
    current = {g.note_id: gold_hash(g) for g in golds}
    return sorted(n for n, h in hashes.items() if current.get(n) != h)


def check_gold(notes: list[GoldNote], code_check: CodeCheck | None = None) -> list[str]:
    """Problems found. Structure always; code validity only when a code_check is given."""
    problems: list[str] = []
    seen: set[str] = set()
    for note in notes:
        where = note.note_id
        if note.note_id in seen:
            problems.append(f"{where}: duplicate note_id")
        seen.add(note.note_id)
        if not re.fullmatch(r"n\d{3}", note.note_id):
            problems.append(f"{where}: note_id must look like n001")
        if not note.expected_codes:
            problems.append(f"{where}: no expected codes")
        codes = [c.code for c in note.expected_codes]
        if len(codes) != len(set(codes)):
            problems.append(f"{where}: duplicate expected code")
        for c in note.expected_codes:
            if not c.reason.strip():
                problems.append(f"{where}: {c.code} has no reason")
            if code_check is not None:
                exists, billable = code_check(c.code, note.visit_date)
                if not exists:
                    problems.append(f"{where}: {c.code} not in the code set for {note.visit_date}")
                elif not billable:
                    problems.append(f"{where}: {c.code} is not billable")
        for rule in note.expected_gap_rules:
            if not RULE_ID.match(rule):
                problems.append(f"{where}: bad rule id {rule!r}")
    return problems
