from app.rules import r2_diabetes_ckd
from tests.unit.rules.helpers import by_code, codes_of, fact, outcomes, run, sug

DM = fact("f1", "type 2 diabetes mellitus", [1])
CKD = fact("f2", "chronic kidney disease", [2], details={"stage": "3b"})


def test_uncomplicated_diabetes_with_ckd_becomes_e11_22() -> None:
    out = run(
        r2_diabetes_ckd.apply, [sug("s1", "E11.9", ["f1"]), sug("s2", "N18.32", ["f2"])], [DM, CKD]
    )

    assert codes_of(out) == ["E11.22", "N18.32"]
    added = by_code(out, "E11.22")
    assert added.added_by_rule == "R2"
    assert (added.fact_ids, added.evidence) == (["f1", "f2"], [1, 2])  # from the facts
    assert [(d.code, d.rule_id) for d in out.dropped] == [("E11.9", "R2")]


def test_diabetes_without_ckd_is_untouched() -> None:
    out = run(r2_diabetes_ckd.apply, [sug("s1", "E11.9", ["f1"])], [DM])

    assert codes_of(out) == ["E11.9"]
    assert out.dropped == []


def test_other_complication_keeps_its_code_and_adds_e11_22() -> None:
    out = run(
        r2_diabetes_ckd.apply,
        [sug("s1", "E11.65", ["f1"]), sug("s2", "N18.4", ["f2"])],
        [DM, CKD],
    )

    assert codes_of(out) == ["E11.22", "E11.65", "N18.4"]


def test_kidney_complication_already_coded_adds_nothing() -> None:
    out = run(
        r2_diabetes_ckd.apply, [sug("s1", "E11.22", ["f1"]), sug("s2", "N18.32", ["f2"])], [DM, CKD]
    )

    assert codes_of(out) == ["E11.22", "N18.32"]


def test_ckd_caused_by_something_else_is_not_presumed() -> None:
    other = fact("f3", "polycystic kidney disease", [3])
    ckd = fact("f2", "chronic kidney disease", [2], caused_by="f3")
    out = run(
        r2_diabetes_ckd.apply,
        [sug("s1", "E11.9", ["f1"]), sug("s2", "N18.32", ["f2"])],
        [DM, ckd, other],
    )

    assert codes_of(out) == ["E11.9", "N18.32"]
    assert outcomes(by_code(out, "E11.9"), "R2") == ["needs_review"]
    assert outcomes(by_code(out, "N18.32"), "R2") == ["needs_review"]


def test_ckd_caused_by_the_diabetes_is_linked() -> None:
    ckd = fact("f2", "chronic kidney disease", [2], caused_by="f1")
    out = run(
        r2_diabetes_ckd.apply, [sug("s1", "E11.9", ["f1"]), sug("s2", "N18.32", ["f2"])], [DM, ckd]
    )

    assert codes_of(out) == ["E11.22", "N18.32"]
