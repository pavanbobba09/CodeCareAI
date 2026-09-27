from app.rules import r7_diabetes_type
from tests.unit.rules.helpers import by_code, fact, outcomes, run, sug


def test_untyped_diabetes_on_e11_needs_review_without_gap() -> None:
    out = run(
        r7_diabetes_type.apply, [sug("s1", "E11.9", ["f1"])], [fact("f1", "diabetes mellitus", [1])]
    )

    assert outcomes(by_code(out, "E11.9"), "R7") == ["needs_review"]
    assert out.gaps == []


def test_typed_diabetes_passes_silently() -> None:
    out = run(
        r7_diabetes_type.apply,
        [sug("s1", "E11.9", ["f1"])],
        [fact("f1", "type 2 diabetes mellitus", [1])],
    )

    assert outcomes(by_code(out, "E11.9"), "R7") == []


def test_type_in_details_or_abbreviation_counts_as_typed() -> None:
    facts = [
        fact("f1", "diabetes mellitus", [1], details={"type": "2"}),
        fact("f2", "DM2", [2]),
    ]
    out = run(
        r7_diabetes_type.apply, [sug("s1", "E11.9", ["f1"]), sug("s2", "E11.65", ["f2"])], facts
    )

    assert outcomes(by_code(out, "E11.9"), "R7") == []
    assert outcomes(by_code(out, "E11.65"), "R7") == []
