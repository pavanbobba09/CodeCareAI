from datetime import date

from app.models.eval import ExpectedCode, GoldNote
from eval.gold import check_gold, load_gold


def _note(**kw: object) -> GoldNote:
    base = {
        "note_id": "n001",
        "visit_date": date(2026, 10, 5),
        "patient_type": "established",
        "text": "Assessment: Essential hypertension.",
        "expected_codes": [ExpectedCode(code="I10", system="ICD-10-CM", reason="documented")],
        "expected_gap_rules": [],
        "expected_em": None,
        "tags": ["htn"],
    }
    return GoldNote.model_validate({**base, **kw})


def test_committed_gold_notes_are_well_formed() -> None:
    notes = load_gold()
    assert len(notes) >= 20
    assert check_gold(notes) == []


def test_gold_notes_have_no_expected_em_until_m6() -> None:
    assert all(n.expected_em is None for n in load_gold())


def test_check_gold_reports_structural_problems() -> None:
    blank = ExpectedCode(code="I10", system="ICD-10-CM", reason=" ")
    problems = check_gold(
        [
            _note(),
            _note(),  # duplicate id
            _note(note_id="x1", expected_codes=[blank], expected_gap_rules=["R15"]),
        ]
    )
    assert problems == [
        "n001: duplicate note_id",
        "x1: note_id must look like n001",
        "x1: I10 has no reason",
        "x1: bad rule id 'R15'",
    ]


def test_check_gold_uses_code_check() -> None:
    def code_check(code: str, visit: date) -> tuple[bool, bool]:
        return {"I10": (True, True), "N18.3": (True, False)}.get(code, (False, False))

    note = _note(
        expected_codes=[
            ExpectedCode(code="N18.3", system="ICD-10-CM", reason="r"),
            ExpectedCode(code="Q99.99", system="ICD-10-CM", reason="r"),
        ]
    )
    assert check_gold([note], code_check) == [
        "n001: N18.3 is not billable",
        "n001: Q99.99 not in the code set for 2026-10-05",
    ]
