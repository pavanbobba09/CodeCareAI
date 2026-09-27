from app.rules import r10_heart_failure_type
from tests.unit.rules.helpers import by_code, codes_of, fact, outcomes, run, sug

HF = [fact("f1", "heart failure", [1])]


def test_untyped_heart_failure_raises_type_gap() -> None:
    out = run(r10_heart_failure_type.apply, [sug("s1", "I50.9", ["f1"])], HF)

    [gap] = out.gaps
    assert (gap.gap_id, gap.rule_id, gap.missing) == ("R10-I50.9", "R10", "heart failure type")


def test_type_without_acuity_raises_acuity_gap() -> None:
    facts = [fact("f1", "systolic heart failure", [1])]
    out = run(r10_heart_failure_type.apply, [sug("s1", "I50.20", ["f1"])], facts)

    [gap] = out.gaps
    assert (gap.gap_id, gap.missing) == ("R10-I50.20", "heart failure acuity")


def test_type_and_acuity_documented_passes() -> None:
    facts = [fact("f1", "chronic systolic heart failure", [1])]
    out = run(r10_heart_failure_type.apply, [sug("s1", "I50.22", ["f1"])], facts)

    assert out.gaps == []
    assert outcomes(by_code(out, "I50.22"), "R10") == ["pass"]


def test_specific_selection_becomes_unspecified_when_type_is_not_documented() -> None:
    out = run(r10_heart_failure_type.apply, [sug("s1", "I50.22", ["f1"])], HF)

    assert codes_of(out) == ["I50.9"]
    assert [g.gap_id for g in out.gaps] == ["R10-I50.9"]


def test_unspecified_selection_becomes_documented_type_and_acuity() -> None:
    facts = [fact("f1", "acute on chronic diastolic heart failure", [1])]
    out = run(r10_heart_failure_type.apply, [sug("s1", "I50.9", ["f1"])], facts)

    assert codes_of(out) == ["I50.33"]
    assert out.gaps == []


def test_wrong_heart_failure_type_is_reconciled() -> None:
    facts = [fact("f1", "acute systolic heart failure", [1])]
    out = run(r10_heart_failure_type.apply, [sug("s1", "I50.32", ["f1"])], facts)

    assert codes_of(out) == ["I50.21"]


def test_i50_without_active_heart_failure_is_not_suggested() -> None:
    history = [fact("f1", "heart failure", [1], status="history")]
    out = run(r10_heart_failure_type.apply, [sug("s1", "I50.22", ["f2"])], history)

    assert outcomes(by_code(out, "I50.22"), "R10") == ["fail"]
    assert out.gaps == []
