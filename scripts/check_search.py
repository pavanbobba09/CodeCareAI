"""Smoke-check candidate search against the loaded code tables (M1 done-when).

Usage: python scripts/check_search.py [--visit-date 2026-10-01]
"""

import argparse
import sys
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models import IndexTerm
from app.db.session import get_engine
from app.models import ClinicalFact, CodeSetSelection
from app.terminology.code_sets import resolve_code_set
from app.terminology.embedder import get_embedder
from app.terminology.search import search_candidates

# (concept, details, exact billable code expected, must appear within top N)
CHECKS = [
    ("type 2 diabetes with CKD", {}, "E11.22", 20),
    ("CKD 3b", {}, "N18.32", 20),
    ("chronic kidney disease", {"stage": "3b"}, "N18.32", 20),
    ("DM2", {}, "E11.9", 20),
    ("HTN", {}, "I10", 20),
    ("HFrEF", {}, "I50.20", 3),
    ("systolic heart failure", {}, "I50.20", 3),
    ("HFpEF", {}, "I50.30", 3),
    ("HFmrEF", {}, "I50.40", 3),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--visit-date", type=date.fromisoformat, default=date(2026, 10, 1))
    args = parser.parse_args()

    failed = 0
    with Session(get_engine()) as session, session.begin():
        # CPT sets arrive in M6; resolve ICD only here.
        sets = CodeSetSelection(
            icd10cm=resolve_code_set(session, "ICD-10-CM", args.visit_date), cpt="none"
        )
        notes = session.scalar(
            select(func.count())
            .select_from(IndexTerm)
            .where(or_(IndexTerm.term.contains("Note:"), IndexTerm.path.contains("Note:")))
        )
        failed += bool(notes)
        print(f"{'PASS' if not notes else 'FAIL'} index rows containing 'Note:' headings: {notes}")
        for concept, details, want, top_n in CHECKS:
            fact = ClinicalFact(
                fact_id="f1",
                kind="condition",
                concept=concept,
                status="active",
                details=details,
                links=[],
                evidence=[1],
            )
            got = search_candidates(session, fact, sets, get_embedder()).candidates
            codes = [c.code for c in got]
            hit = codes.index(want) if want in codes else None
            ok = hit is not None and hit < top_n
            failed += not ok
            print(
                f"{'PASS' if ok else 'FAIL'} {concept!r} {details} -> want {want} "
                f"at rank {None if hit is None else hit + 1}; top5 {codes[:5]}"
            )
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
