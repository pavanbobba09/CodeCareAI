from app.rules import r6_duplicate_hypertension
from tests.unit.rules.helpers import by_code, codes_of, fact, outcomes, run, sug

HTN = [fact("f1", "hypertension", [1])]


def test_i10_removed_next_to_i12() -> None:
    out = run(
        r6_duplicate_hypertension.apply,
        [sug("s1", "I10", ["f1"]), sug("s2", "I12.9", ["f1"])],
        HTN,
    )

    assert codes_of(out) == ["I12.9"]
    assert [(d.code, d.rule_id) for d in out.dropped] == [("I10", "R6")]


def test_i13_replaces_i10_i11_and_i12() -> None:
    sugs = [
        sug("s1", "I10", ["f1"]),
        sug("s2", "I11.0", ["f1"]),
        sug("s3", "I12.9", ["f1"]),
        sug("s4", "I13.0", ["f1"]),
    ]
    out = run(r6_duplicate_hypertension.apply, sugs, HTN)

    assert codes_of(out) == ["I13.0"]


def test_i10_alone_is_kept() -> None:
    out = run(
        r6_duplicate_hypertension.apply, [sug("s1", "I10", ["f1"]), sug("s2", "E11.9", ["f2"])], []
    )

    assert codes_of(out) == ["E11.9", "I10"]
    assert out.dropped == []


def test_i10_without_active_hypertension_is_not_suggested() -> None:
    history = [fact("f1", "hypertension", [1], status="history")]
    out = run(r6_duplicate_hypertension.apply, [sug("s1", "I10", ["f2"])], history)

    assert outcomes(by_code(out, "I10"), "R6") == ["fail"]
