"""Check every gold note: structure, reasons, rule ids, and that each expected code is
billable in the ICD-10-CM set for its visit date (needs the loaded tables).

Usage: python scripts/validate_gold.py
"""

import sys
from datetime import date

from sqlalchemy.orm import Session

from _common import REPO
from app.db.session import get_engine
from app.terminology.code_sets import CodeSetMissingError, resolve_code_set
from app.terminology.lookup import DbCodeLookup

sys.path.insert(0, str(REPO))
from eval.gold import check_gold, load_gold


def main() -> None:
    notes = load_gold()
    with Session(get_engine()) as session:
        lookup = DbCodeLookup(session)

        def code_check(code: str, visit: date) -> tuple[bool, bool]:
            try:
                cs = resolve_code_set(session, "ICD-10-CM", visit)
            except CodeSetMissingError:
                return False, False
            return lookup.get_code(code, cs) is not None, lookup.is_billable(code, cs)

        problems = check_gold(notes, code_check)
    n_codes = sum(len(n.expected_codes) for n in notes)
    for p in problems:
        print(f"FAIL {p}")
    print(f"{len(notes)} gold notes, {n_codes} expected codes, {len(problems)} problems")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
