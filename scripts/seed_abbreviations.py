"""Load data/abbreviations.csv into the abbreviations table (replaces existing rows).

Usage: python scripts/seed_abbreviations.py
"""

import csv

from sqlalchemy import delete, insert
from sqlalchemy.orm import Session

from _common import DATA
from app.db.models import Abbreviation
from app.db.session import get_engine


def main() -> None:
    with open(DATA / "abbreviations.csv", newline="") as f:
        rows = [{"abbr": r["abbr"].upper(), "expansion": r["expansion"]} for r in csv.DictReader(f)]
    with Session(get_engine()) as session, session.begin():
        session.execute(delete(Abbreviation))
        session.execute(insert(Abbreviation), rows)
    print(f"abbreviations: {len(rows)} rows")


if __name__ == "__main__":
    main()
