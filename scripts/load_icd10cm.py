"""Download and load one ICD-10-CM fiscal-year release from CMS.

Usage: python scripts/load_icd10cm.py --fy 2027 [--embed]
"""

import argparse
import time

from sqlalchemy.orm import Session

from _common import DATA
from app.db.session import get_engine
from app.loaders.icd10cm import RELEASES, download, parse_release, store_release
from app.terminology.embed_codes import embed_code_set
from app.terminology.embedder import get_embedder


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fy", type=int, required=True, choices=sorted(RELEASES))
    parser.add_argument("--embed", action="store_true", help="also compute code embeddings")
    args = parser.parse_args()

    release = RELEASES[args.fy]
    raw_dir = DATA / "raw" / f"fy{release.fy}"
    t0 = time.time()
    download(release, raw_dir)
    parsed = parse_release(release, raw_dir)
    with Session(get_engine()) as session, session.begin():
        store_release(session, release, parsed)
    billable = sum(c.billable for c in parsed.codes)
    print(
        f"{release.code_set_id}: {len(parsed.codes)} codes ({billable} billable), "
        f"{len(parsed.index)} index terms in {time.time() - t0:.1f}s"
    )

    if args.embed:
        t0 = time.time()
        with Session(get_engine()) as session:
            n = embed_code_set(session, release.code_set_id, get_embedder())
        print(f"{release.code_set_id}: embedded {n} codes in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
