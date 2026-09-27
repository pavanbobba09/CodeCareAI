from app.rules import r12_excludes1
from app.terminology.tabular import code_refs, matches
from tests.unit.rules.helpers import LOOKUP, by_code, codes_of, outcomes, run, sug


def test_type_1_and_type_2_diabetes_conflict_via_category_note() -> None:
    out = run(r12_excludes1.apply, [sug("s1", "E10.9", ["f1"]), sug("s2", "E11.9", ["f2"])], [])

    [gap] = out.gaps
    assert (gap.gap_id, gap.kind, gap.affects_codes) == (
        "R12-E10.9-E11.9",
        "conflicting",
        ["E10.9", "E11.9"],
    )
    assert codes_of(out) == ["E10.9", "E11.9"]  # never dropped
    assert outcomes(by_code(out, "E11.9"), "R12") == ["needs_review"]


def test_unrelated_codes_do_not_conflict() -> None:
    out = run(r12_excludes1.apply, [sug("s1", "E11.22", ["f1"]), sug("s2", "N18.32", ["f2"])], [])

    assert out.gaps == []


def test_excludes1_is_inherited_from_the_category() -> None:
    assert "I50.4" in LOOKUP.excludes1_of("I50.20", "ICD10CM-FY2027")
    out = run(r12_excludes1.apply, [sug("s1", "I50.20", ["f1"]), sug("s2", "I50.42", ["f2"])], [])
    assert [g.gap_id for g in out.gaps] == ["R12-I50.20-I50.42"]


def test_code_refs_parse_codes_categories_and_ranges() -> None:
    assert code_refs("type 1 diabetes mellitus (E10.-)") == ["E10"]
    assert code_refs("hypertensive disease complicating pregnancy (O10-O11, O13-O16)") == [
        "O10-O11",
        "O13-O16",
    ]
    assert code_refs("combined systolic and diastolic heart failure (I50.4-)") == ["I50.4"]
    assert code_refs("neonatal diabetes mellitus (P70.2)") == ["P70.2"]
    assert code_refs("no codes here (congenital)") == []


def test_matches_codes_categories_and_ranges() -> None:
    assert matches("E10", "E10.65")
    assert not matches("E10", "E11.65")
    assert matches("O10-O11", "O11.3")
    assert not matches("O10-O11", "O12.0")
    assert matches("I50.4", "I50.42")
