from datetime import date

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.db.models import Code, CodeSet, IndexTerm
from app.models import ClinicalFact, CodeSetSelection
from app.terminology.abbreviations import expand, load_abbreviations
from app.terminology.code_sets import CodeSetMissingError, resolve_code_sets
from app.terminology.lookup import DbCodeLookup, preload_lookup
from app.terminology.search import MAX_CANDIDATES, index_hits, search_candidates
from tests.integration.conftest import FakeEmbedder

pytestmark = pytest.mark.integration

SETS = CodeSetSelection(icd10cm="ICD10CM-FY2027", cpt=None)


def _fact(concept: str, details: dict[str, str] | None = None) -> ClinicalFact:
    return ClinicalFact(
        fact_id="f1",
        kind="condition",
        concept=concept,
        status="active",
        details=details or {},
        links=[],
        evidence=[1],
    )


def _codes(seeded: Engine, concept: str, details: dict[str, str] | None = None) -> list[str]:
    with Session(seeded) as session, session.begin():
        result = search_candidates(session, _fact(concept, details), SETS, FakeEmbedder())
    return [c.code for c in result.candidates]


def test_resolve_code_sets_on_first_day(seeded: Engine) -> None:
    with Session(seeded) as session:
        assert resolve_code_sets(session, date(2026, 10, 1)) == SETS
        assert resolve_code_sets(session, date(2027, 9, 30)) == SETS


def test_resolve_code_sets_uses_cpt_set_when_one_covers_the_date(seeded: Engine) -> None:
    with Session(seeded) as session:
        session.add(
            CodeSet(
                id="CPT-TEST-2026",
                system="CPT",
                valid_from=date(2026, 11, 1),
                valid_to=None,
                source_url=None,
            )
        )
        session.flush()
        assert resolve_code_sets(session, date(2026, 11, 1)).cpt == "CPT-TEST-2026"
        assert resolve_code_sets(session, date(2026, 10, 31)).cpt is None
        session.rollback()


def test_resolve_code_sets_missing(seeded: Engine) -> None:
    with Session(seeded) as session, pytest.raises(CodeSetMissingError) as err:
        resolve_code_sets(session, date(2026, 9, 30))
    assert err.value.system == "ICD-10-CM"


def test_diabetes_with_ckd_finds_e11_22(seeded: Engine) -> None:
    assert "E11.22" in _codes(seeded, "type 2 diabetes with CKD")


def test_ckd_3b_finds_n18_32(seeded: Engine) -> None:
    assert "N18.32" in _codes(seeded, "CKD 3b")
    assert "N18.32" in _codes(seeded, "chronic kidney disease", {"stage": "3b"})


def test_index_category_hit_expands_to_billable_children(seeded: Engine) -> None:
    codes = _codes(seeded, "hypertension with heart failure")
    assert any(c.startswith("I50.") for c in codes)


def test_candidates_are_real_billable_and_capped(seeded: Engine) -> None:
    with Session(seeded) as session, session.begin():
        result = search_candidates(session, _fact("type 2 diabetes with CKD"), SETS, FakeEmbedder())
        rows = session.execute(
            select(Code.code, Code.billable).where(Code.code_set_id == SETS.icd10cm)
        )
        billable = {code: flag for code, flag in rows}

    assert 0 < len(result.candidates) <= MAX_CANDIDATES
    assert result.fact_id == "f1"
    for cand in result.candidates:
        assert billable.get(cand.code) is True
        assert cand.system == "ICD-10-CM"
        assert cand.sources


def test_abbreviation_source_only_when_expanded(seeded: Engine) -> None:
    with Session(seeded) as session, session.begin():
        abbr = search_candidates(session, _fact("CKD 3b"), SETS, FakeEmbedder())
        plain = search_candidates(
            session, _fact("chronic kidney disease stage 3b"), SETS, FakeEmbedder()
        )
    assert all("abbreviation" in c.sources for c in abbr.candidates)
    assert all("abbreviation" not in c.sources for c in plain.candidates)


def test_procedure_searches_cpt_set(seeded: Engine) -> None:
    fact = _fact("basic metabolic panel").model_copy(update={"kind": "procedure"})
    with Session(seeded) as session, session.begin():
        result = search_candidates(session, fact, SETS, FakeEmbedder())
    assert result.candidates == []  # no CPT set covers the visit date


def test_lookup(seeded: Engine) -> None:
    with Session(seeded) as session:
        lookup = DbCodeLookup(session)
        found = lookup.get_code("E11.22", SETS.icd10cm)
        assert found is not None
        assert found.description.startswith("Type 2 diabetes mellitus with diabetic chronic")
        assert lookup.get_code("E11.22", "ICD10CM-FY1999") is None
        assert lookup.get_code("Q99.99", SETS.icd10cm) is None

        assert lookup.children_of("N18.3", SETS.icd10cm) == ["N18.30", "N18.31", "N18.32"]
        assert lookup.children_of("N18.32", SETS.icd10cm) == []

        assert lookup.is_billable("N18.32", SETS.icd10cm) is True
        assert lookup.is_billable("N18.3", SETS.icd10cm) is False
        assert lookup.is_billable("Q99.99", SETS.icd10cm) is False


@pytest.mark.parametrize(
    ("concept", "want"),
    [
        ("HFrEF", "I50.20"),
        ("systolic heart failure", "I50.20"),
        ("HFpEF", "I50.30"),
    ],
)
def test_heart_failure_type_finds_unspecified_acuity_code_top3(
    seeded: Engine, concept: str, want: str
) -> None:
    # HFrEF = systolic, HFpEF = diastolic (FY2027 Index); no acuity documented.
    assert want in _codes(seeded, concept)[:3]


@pytest.mark.parametrize(
    ("concept", "want"),
    [
        ("HFrEF", "I50.20"),
        ("systolic heart failure", "I50.20"),
        ("HFpEF", "I50.30"),
    ],
)
def test_heart_failure_index_source_ranks_type_code_first(
    seeded: Engine, concept: str, want: str
) -> None:
    # The fixture is too small for the merged ranking to expose index bugs, so check
    # the index source alone: "Note:" heading text once hid I50.20 from it.
    with Session(seeded) as session, session.begin():
        query, _ = expand(concept, load_abbreviations(session))
        assert index_hits(session, query, SETS.icd10cm)[0] == want


def test_no_note_heading_text_in_index_search_text(seeded: Engine) -> None:
    with Session(seeded) as session:
        leaked = session.scalars(
            select(IndexTerm.term).where(
                IndexTerm.term.contains("Note:") | IndexTerm.path.contains("Note:")
            )
        ).all()
    assert leaked == []


def test_excludes1_is_inherited_from_the_category(seeded: Engine) -> None:
    # E11 carries "type 1 diabetes mellitus (E10.-)"; it applies to every E11 code.
    with Session(seeded) as session:
        assert DbCodeLookup(session).excludes1_of("E11.22", SETS.icd10cm) == ["E10"]
        preloaded = preload_lookup(session, {SETS.icd10cm: {"E11.22"}})
    assert preloaded.excludes1_of("E11.22", SETS.icd10cm) == ["E10"]
    assert preloaded.get_code("E11", SETS.icd10cm) is not None  # ancestor loaded
