from datetime import date

from app.models import CodeSetSelection, RuleInput, Suggestion
from app.rules import r1_code_validity, run_all
from app.terminology.lookup import CodeRecord, InMemoryCodeLookup

SETS = CodeSetSelection(icd10cm="ICD10CM-FY2027", cpt=None)
LOOKUP = InMemoryCodeLookup(
    {
        ("ICD10CM-FY2027", "E11.22"): CodeRecord(
            "E11.22", "ICD-10-CM", "Type 2 diabetes mellitus with diabetic CKD", True, "E11.2"
        ),
        ("ICD10CM-FY2027", "N18.3"): CodeRecord(
            "N18.3", "ICD-10-CM", "Chronic kidney disease, stage 3 (moderate)", False, "N18"
        ),
        ("ICD10CM-FY2026", "Q99.98"): CodeRecord(
            "Q99.98", "ICD-10-CM", "Only in the older release", True, None
        ),
    }
)


def _s(code: str, system: str = "ICD-10-CM") -> Suggestion:
    return Suggestion.model_validate(
        {
            "suggestion_id": "s1",
            "code": code,
            "system": system,
            "description": "d",
            "fact_ids": ["f1"],
            "evidence": [1],
            "rule_results": [],
            "gap_ids": [],
            "confidence": "review",
        }
    )


def _run(*suggestions: Suggestion) -> tuple[list[str], list[tuple[str, str]]]:
    inp = RuleInput(
        visit_date=date(2026, 10, 15), code_sets=SETS, facts=[], suggestions=list(suggestions)
    )
    out = r1_code_validity.apply(inp, LOOKUP)
    return [s.code for s in out.suggestions], [(d.code, d.reason) for d in out.dropped]


def test_valid_billable_code_passes_with_result() -> None:
    inp = RuleInput(
        visit_date=date(2026, 10, 15), code_sets=SETS, facts=[], suggestions=[_s("E11.22")]
    )
    [kept] = r1_code_validity.apply(inp, LOOKUP).suggestions

    [result] = kept.rule_results
    assert (result.rule_id, result.outcome, result.affects_codes) == ("R1", "pass", ["E11.22"])
    assert "45 CFR 162.1002" in result.source_ref


def test_absent_code_is_dropped() -> None:
    kept, dropped = _run(_s("Z99.999"))
    assert kept == []
    assert dropped[0][0] == "Z99.999"
    assert "not in ICD10CM-FY2027" in dropped[0][1]


def test_non_billable_category_is_dropped() -> None:
    kept, dropped = _run(_s("N18.3"))
    assert kept == []
    assert "not billable" in dropped[0][1]


def test_code_valid_only_in_another_release_is_dropped() -> None:
    kept, dropped = _run(_s("Q99.98"))
    assert kept == []
    assert "not in ICD10CM-FY2027" in dropped[0][1]


def test_cpt_code_without_cpt_set_is_dropped() -> None:
    kept, dropped = _run(_s("80048", system="CPT"))
    assert kept == []
    assert "No CPT code set covers" in dropped[0][1]


def test_run_all_keeps_valid_and_reports_dropped() -> None:
    inp = RuleInput(
        visit_date=date(2026, 10, 15),
        code_sets=SETS,
        facts=[],
        suggestions=[_s("E11.22"), _s("N18.3")],
    )
    out = run_all(inp, LOOKUP)
    assert [s.code for s in out.suggestions] == ["E11.22"]
    assert [d.code for d in out.dropped] == ["N18.3"]
