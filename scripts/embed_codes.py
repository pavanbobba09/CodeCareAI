"""Compute missing code embeddings for one code set. Safe to rerun; it resumes.

Usage: python scripts/embed_codes.py --code-set ICD10CM-FY2027
"""

import argparse
import time

from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.terminology.embed_codes import embed_code_set
from app.terminology.embedder import get_embedder


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--code-set", required=True)
    args = parser.parse_args()

    t0 = time.time()
    with Session(get_engine()) as session:
        n = embed_code_set(session, args.code_set, get_embedder())
    print(f"{args.code_set}: embedded {n} codes in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
