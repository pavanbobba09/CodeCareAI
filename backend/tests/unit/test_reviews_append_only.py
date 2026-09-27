"""CLAUDE.md rule 8: reviews are append-only. No code path may update or delete them.

The db trigger (migration 0001) is the backstop; this keeps the code honest too.
"""

import re
from pathlib import Path

APP = Path(__file__).parents[2] / "app"
# Update or delete paths on the reviews table only: SQLAlchemy update()/delete() on ReviewRow,
# session.delete() of a review object, or raw SQL against `reviews`.
FORBIDDEN = re.compile(
    r"update\(\s*ReviewRow|delete\(\s*ReviewRow|session\.delete\([^)]*review"
    r"|UPDATE\s+reviews\b|DELETE\s+FROM\s+reviews\b",
    re.IGNORECASE,
)


def test_no_update_or_delete_of_reviews_in_app_code() -> None:
    hits = [
        f"{path.relative_to(APP)}:{n}: {line.strip()}"
        for path in APP.rglob("*.py")
        for n, line in enumerate(path.read_text().splitlines(), 1)
        if FORBIDDEN.search(line)
    ]
    assert hits == []


def test_the_scan_catches_what_it_should() -> None:
    for bad in (
        "session.execute(update(ReviewRow).values(action='accept'))",
        "session.execute(delete(ReviewRow))",
        "session.delete(review_row)",
        'text("UPDATE reviews SET action = :a")',
        'text("delete from reviews")',
    ):
        assert FORBIDDEN.search(bad), bad


def test_the_scan_leaves_other_tables_alone() -> None:
    for fine in (
        "session.delete(note_row)",
        "session.execute(delete(AnalysisRow))",
        'text("DELETE FROM notes")',
        "session.execute(select(ReviewRow))",
        'text("UPDATE reviews_archive SET x = 1")',
    ):
        assert not FORBIDDEN.search(fine), fine
