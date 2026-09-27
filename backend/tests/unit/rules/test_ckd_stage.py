"""Documented CKD stage: R2/R3/R5 add the N18 code; R9 raises a gap only when no stage."""

from app.rules import r2_diabetes_ckd, r3_htn_ckd, r5_htn_hf_ckd, r9_ckd_stage
from app.rules.common import documented_stage_code
from tests.unit.rules.helpers import by_code, codes_of, fact, outcomes, run, run_chain, sug

HTN = fact("f1", "hypertension", [1])
HF = fact("f2", "chronic systolic heart failure", [2])


def test_stage_is_read_from_details_or_concept() -> None:
    assert (
        documented_stage_code(fact("f", "chronic kidney disease", [1], details={"stage": "5"}))
        == "N18.5"
    )
    assert documented_stage_code(fact("f", "CKD stage 3b", [1])) == "N18.32"
    assert documented_stage_code(fact("f", "end-stage renal disease", [1])) == "N18.6"
    assert documented_stage_code(fact("f", "chronic kidney disease", [1])) is None


def test_n007_i12_0_on_combined_fact_gets_n18_5() -> None:
    combined = fact("f1", "hypertension with chronic kidney disease stage 5", [4])
    out = run(r3_htn_ckd.apply, [sug("s1", "I12.0", ["f1"], [4])], [combined])

    n18 = by_code(out, "N18.5")
    assert (n18.added_by_rule, n18.fact_ids, n18.evidence) == ("R3", ["f1"], [4])
    assert codes_of(out) == ["I12.0", "N18.5"]


def test_r3_adds_i12_and_the_documented_stage_when_no_n18_was_picked() -> None:
    ckd = fact("f3", "chronic kidney disease", [3], details={"stage": "4"})
    out = run(r3_htn_ckd.apply, [sug("s1", "I10", ["f1"])], [HTN, ckd])

    assert codes_of(out) == ["I10", "I12.9", "N18.4"]


def test_r3_selected_n18_is_not_duplicated() -> None:
    ckd = fact("f3", "chronic kidney disease", [3], details={"stage": "4"})
    out = run(r3_htn_ckd.apply, [sug("s1", "I10", ["f1"]), sug("s2", "N18.4", ["f3"])], [HTN, ckd])

    assert codes_of(out) == ["I10", "I12.9", "N18.4"]


def test_r5_adds_i13_and_the_documented_stage() -> None:
    ckd = fact("f3", "CKD", [3], details={"stage": "3b"})
    out = run(
        r5_htn_hf_ckd.apply, [sug("s1", "I10", ["f1"]), sug("s2", "I50.22", ["f2"])], [HTN, HF, ckd]
    )

    assert codes_of(out) == ["I10", "I13.0", "I50.22", "N18.32"]
    assert by_code(out, "N18.32").added_by_rule == "R5"


def test_r2_e11_22_alone_gets_its_stage_code() -> None:
    dm_ckd = fact("f1", "type 2 diabetes mellitus with chronic kidney disease stage 3a", [1])
    out = run(r2_diabetes_ckd.apply, [sug("s1", "E11.22", ["f1"])], [dm_ckd])

    assert codes_of(out) == ["E11.22", "N18.31"]


def test_r2_e11_9_with_staged_ckd_fact_becomes_e11_22_and_stage() -> None:
    dm = fact("f1", "type 2 diabetes mellitus", [1])
    ckd = fact("f2", "chronic kidney disease", [2], details={"stage": "3a"})
    out = run(r2_diabetes_ckd.apply, [sug("s1", "E11.9", ["f1"])], [dm, ckd])

    assert codes_of(out) == ["E11.22", "N18.31"]


def test_unstaged_ckd_gets_n18_9_and_the_r9_gap() -> None:
    ckd = fact("f3", "chronic kidney disease", [3])
    out = run_chain([sug("s1", "I10", ["f1"])], [HTN, ckd])

    assert codes_of(out) == ["I12.9", "N18.9"]
    assert [g.gap_id for g in out.gaps] == ["R9-N18.9"]
    assert [r.rule_id for r in by_code(out, "N18.9").rule_results] == ["R3", "R9", "R1"]


def test_r9_documented_stage_replaces_n18_9_without_gap() -> None:
    ckd = fact("f1", "chronic kidney disease", [2], details={"stage": "4"})
    out = run(r9_ckd_stage.apply, [sug("s1", "N18.9", ["f1"])], [ckd])

    assert codes_of(out) == ["N18.4"]
    assert out.gaps == []
    assert [(d.code, d.rule_id) for d in out.dropped] == [("N18.9", "R9")]
    assert outcomes(by_code(out, "N18.4"), "R9") == ["pass"]


def test_r9_documented_substage_replaces_n18_30() -> None:
    ckd = fact("f1", "CKD stage 3b", [2])
    out = run(r9_ckd_stage.apply, [sug("s1", "N18.30", ["f1"])], [ckd])

    assert codes_of(out) == ["N18.32"]
    assert out.gaps == []


def test_r9_gap_stays_when_the_note_has_no_stage() -> None:
    ckd = fact("f1", "chronic kidney disease", [2])
    out = run(r9_ckd_stage.apply, [sug("s1", "N18.9", ["f1"])], [ckd])

    assert codes_of(out) == ["N18.9"]
    assert [g.gap_id for g in out.gaps] == ["R9-N18.9"]


def test_n007_through_the_chain_has_no_gap_and_passes_r1() -> None:
    combined = fact("f1", "hypertension with chronic kidney disease stage 5", [4])
    out = run_chain([sug("s1", "I12.0", ["f1"], [4])], [combined])

    assert codes_of(out) == ["I12.0", "N18.5"]
    assert out.gaps == []
    assert "R1" in [r.rule_id for r in by_code(out, "N18.5").rule_results]
