"""CLAUDE.md rule 8: reviews are append-only. No code path may update or delete them.

The db trigger (migration 0001) is the backstop; this keeps the code honest too.
"""

import re
from pathlib import Path

APP = Path(__file__).parents[2] / "app"
FORBIDDEN = re.compile(
    r"update\(\s*ReviewRow|delete\(\s*ReviewRow|session\.delete\(|UPDATE\s+reviews|DELETE\s+FROM\s+reviews",
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
        "session.delete(row)",
        'text("UPDATE reviews SET action = :a")',
        'text("delete from reviews")',
    ):
        assert FORBIDDEN.search(bad), bad
