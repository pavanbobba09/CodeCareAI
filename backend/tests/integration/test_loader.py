from datetime import date

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.db.models import Code, IndexTerm
from app.loaders.icd10cm import IndexRow, OrderRow, ParsedRelease, Release, store_release

pytestmark = pytest.mark.integration

# Separate code set so the shared `seeded` fixture is untouched.
RELEASE = Release(
    fy=2099,
    valid_from=date(2098, 10, 1),
    valid_to=date(2099, 9, 30),
    order_zip="unused",
    tables_zip="unused",
)


def _parsed(codes: list[OrderRow]) -> ParsedRelease:
    return ParsedRelease(
        codes=codes,
        parents={c.code: None for c in codes},
        notes={},
        index=[IndexRow(term="Hypertension", path="Hypertension", code="I10")],
    )


def test_reload_keeps_embeddings_for_unchanged_descriptions(engine: Engine) -> None:
    first = _parsed(
        [
            OrderRow("I10", True, "Essential (primary) hypertension"),
            OrderRow("N18.32", True, "Chronic kidney disease, stage 3b"),
            OrderRow("Q99.98", True, "Code removed next release"),
        ]
    )
    with Session(engine) as session, session.begin():
        store_release(session, RELEASE, first)
        for code in session.scalars(select(Code).where(Code.code_set_id == "ICD10CM-FY2099")):
            code.embedding = [0.1] * 384

    second = _parsed(
        [
            OrderRow("I10", True, "Essential (primary) hypertension"),
            OrderRow("N18.32", True, "Chronic kidney disease, stage 3b (reworded)"),
        ]
    )
    with Session(engine) as session, session.begin():
        store_release(session, RELEASE, second)

    with Session(engine) as session:
        rows = {
            c.code: c
            for c in session.scalars(select(Code).where(Code.code_set_id == "ICD10CM-FY2099"))
        }
        assert set(rows) == {"I10", "N18.32"}
        assert rows["I10"].embedding is not None
        assert rows["N18.32"].embedding is None
        assert rows["N18.32"].description.endswith("(reworded)")
        index_count = len(
            session.scalars(
                select(IndexTerm).where(IndexTerm.code_set_id == "ICD10CM-FY2099")
            ).all()
        )
        assert index_count == 1
