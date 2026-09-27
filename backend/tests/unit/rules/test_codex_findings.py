"""Regression tests for the Codex review findings (2026-09-27). Each feeds in a
wrong-but-valid code and fails on the rules as they were before the fix."""

from app.models import RuleOutput
from app.rules import (
    r2_diabetes_ckd,
    r3_htn_ckd,
    r4_htn_hf,
    r5_htn_hf_ckd,
    r7_diabetes_type,
    r9_ckd_stage,
)
from app.rules.common import not_suggested
from tests.unit.rules.helpers import by_code, codes_of, fact, outcomes, run, run_chain, sug

HTN = fact("f1", "hypertension", [1])
HF = fact("f2", "chronic systolic heart failure", [2])


def _live(out: RuleOutput) -> list[str]:
    return sorted(s.code for s in out.suggestions if not not_suggested(s))


# Finding 2: combination codes need their documented parts; presence comes from facts only.


def test_i12_without_documented_ckd_is_not_suggested() -> None:
    out = run(r3_htn_ckd.apply, [sug("s1", "I12.9", ["f1"])], [HTN])

    assert outcomes(by_code(out, "I12.9"), "R3") == ["fail"]
    assert _live(out) == []


def test_i13_without_documented_heart_failure_is_not_suggested() -> None:
    ckd = fact("f3", "chronic kidney disease", [3], details={"stage": "4"})
    sugs = [sug("s1", "I13.0", ["f1"]), sug("s2", "N18.4", ["f3"])]
    out = run(r5_htn_hf_ckd.apply, sugs, [HTN, ckd])

    assert outcomes(by_code(out, "I13.0"), "R5") == ["fail"]


def test_e11_22_without_documented_ckd_is_not_suggested() -> None:
    out = run(
        r2_diabetes_ckd.apply, [sug("s1", "E11.22", ["f1"])], [fact("f1", "type 2 diabetes", [1])]
    )

    assert outcomes(by_code(out, "E11.22"), "R2") == ["fail"]
    assert "N18.9" not in codes_of(out)  # no stage code invented for undocumented CKD


def test_i11_0_without_documented_heart_failure_is_not_suggested() -> None:
    out = run(r4_htn_hf.apply, [sug("s1", "I11.0", ["f1"])], [HTN])

    assert outcomes(by_code(out, "I11.0"), "R4") == ["fail"]


def test_n007_stage_comes_from_the_fact_not_the_selected_code() -> None:
    # The LLM picked I12.0 (stage 5 variant) but the fact documents stage 4.
    combined = fact("f1", "hypertension with chronic kidney disease", [4], details={"stage": "4"})
    out = run_chain([sug("s1", "I12.0", ["f1"], [4])], [combined])

    assert codes_of(out) == ["I12.9", "N18.4"]


# Finding 3: reconcile every selected N18 code with the documented stage, both ways.


def test_selected_stage_differs_from_documented_stage() -> None:
    ckd = fact("f1", "chronic kidney disease", [1], details={"stage": "3b"})
    out = run(r9_ckd_stage.apply, [sug("s1", "N18.4", ["f1"])], [ckd])

    assert codes_of(out) == ["N18.32"]


def test_selected_substage_without_documented_substage_goes_down_with_gap() -> None:
    ckd = fact("f1", "chronic kidney disease", [1], details={"stage": "3"})
    out = run(r9_ckd_stage.apply, [sug("s1", "N18.32", ["f1"])], [ckd])

    assert codes_of(out) == ["N18.30"]
    assert [g.gap_id for g in out.gaps] == ["R9-N18.30"]


def test_stage_5_and_esrd_documented_gives_n18_6() -> None:
    facts = [fact("f1", "CKD stage 5", [1]), fact("f2", "end-stage renal disease", [2])]
    out = run(r9_ckd_stage.apply, [sug("s1", "N18.5", ["f1"])], facts)

    assert codes_of(out) == ["N18.6"]


def test_selected_esrd_with_only_stage_5_documented_goes_to_n18_5() -> None:
    out = run(r9_ckd_stage.apply, [sug("s1", "N18.6", ["f1"])], [fact("f1", "CKD stage 5", [1])])

    assert codes_of(out) == ["N18.5"]


def test_n18_code_without_documented_ckd_is_not_suggested() -> None:
    out = run(r9_ckd_stage.apply, [sug("s1", "N18.4", ["f1"])], [HTN])

    assert outcomes(by_code(out, "N18.4"), "R9") == ["fail"]


# Finding 4: exactly one mutually exclusive variant, chosen from documented facts.


def test_both_i12_variants_leave_only_the_documented_one() -> None:
    ckd = fact("f3", "CKD", [3], details={"stage": "5"})
    sugs = [
        sug("s1", "I12.9", ["f1", "f3"]),
        sug("s2", "I12.0", ["f1", "f3"]),
        sug("s3", "N18.5", ["f3"]),
    ]
    out = run(r3_htn_ckd.apply, sugs, [HTN, ckd])

    assert [c for c in codes_of(out) if c.startswith("I12")] == ["I12.0"]


def test_i13_2_with_stage_3a_documented_becomes_i13_0() -> None:
    ckd = fact("f3", "CKD", [3], details={"stage": "3a"})
    sugs = [
        sug("s1", "I13.2", ["f1", "f2", "f3"]),
        sug("s2", "I50.22", ["f2"]),
        sug("s3", "N18.31", ["f3"]),
    ]
    out = run(r5_htn_hf_ckd.apply, sugs, [HTN, HF, ckd])

    assert [c for c in codes_of(out) if c.startswith("I13")] == ["I13.0"]


def test_i11_9_with_documented_heart_failure_becomes_i11_0() -> None:
    out = run(r4_htn_hf.apply, [sug("s1", "I11.9", ["f1"]), sug("s2", "I50.22", ["f2"])], [HTN, HF])

    assert [c for c in codes_of(out) if c.startswith("I11")] == ["I11.0"]


# Finding 5: R7 replaces E10/E13 with E11 when no type is documented.


def test_untyped_e10_becomes_e11_for_review() -> None:
    out = run(
        r7_diabetes_type.apply, [sug("s1", "E10.9", ["f1"])], [fact("f1", "diabetes mellitus", [1])]
    )

    assert codes_of(out) == ["E11.9"]
    assert outcomes(by_code(out, "E11.9"), "R7") == ["needs_review"]


def test_untyped_e13_becomes_e11() -> None:
    out = run(r7_diabetes_type.apply, [sug("s1", "E13.9", ["f1"])], [fact("f1", "diabetes", [1])])

    assert codes_of(out) == ["E11.9"]


def test_documented_type_1_keeps_e10() -> None:
    out = run(
        r7_diabetes_type.apply,
        [sug("s1", "E10.9", ["f1"])],
        [fact("f1", "type 1 diabetes mellitus", [1])],
    )

    assert codes_of(out) == ["E10.9"]


# Finding 6: R2 adds E11.22 next to other kidney complications; only E11.9 is replaced.


def test_e11_21_with_documented_ckd_gets_e11_22_alongside() -> None:
    dm = fact("f1", "type 2 diabetes mellitus with diabetic nephropathy", [1])
    ckd = fact("f2", "chronic kidney disease", [2], details={"stage": "3a"})
    sugs = [sug("s1", "E11.21", ["f1"]), sug("s2", "N18.31", ["f2"])]
    out = run(r2_diabetes_ckd.apply, sugs, [dm, ckd])

    assert codes_of(out) == ["E11.21", "E11.22", "N18.31"]
