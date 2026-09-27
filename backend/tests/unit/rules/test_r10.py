from app.rules import r10_heart_failure_type
from tests.unit.rules.helpers import by_code, fact, outcomes, run, sug

HF = [fact("f1", "heart failure", [1])]


def test_untyped_heart_failure_raises_type_gap() -> None:
    out = run(r10_heart_failure_type.apply, [sug("s1", "I50.9", ["f1"])], HF)

    [gap] = out.gaps
    assert (gap.gap_id, gap.rule_id, gap.missing) == ("R10-I50.9", "R10", "heart failure type")


def test_type_without_acuity_raises_acuity_gap() -> None:
    out = run(r10_heart_failure_type.apply, [sug("s1", "I50.20", ["f1"])], HF)

    [gap] = out.gaps
    assert (gap.gap_id, gap.missing) == ("R10-I50.20", "heart failure acuity")


def test_type_and_acuity_documented_passes() -> None:
    out = run(r10_heart_failure_type.apply, [sug("s1", "I50.22", ["f1"])], HF)

    assert out.gaps == []
    assert outcomes(by_code(out, "I50.22"), "R10") == ["pass"]


def test_i50_without_active_heart_failure_is_not_suggested() -> None:
    history = [fact("f1", "heart failure", [1], status="history")]
    out = run(r10_heart_failure_type.apply, [sug("s1", "I50.22", ["f2"])], history)

    assert outcomes(by_code(out, "I50.22"), "R10") == ["fail"]
    assert out.gaps == []
