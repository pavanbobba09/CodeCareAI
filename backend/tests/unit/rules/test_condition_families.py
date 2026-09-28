import pytest

from app.models import ClinicalFact
from app.rules import (
    Rule,
    r2_diabetes_ckd,
    r3_htn_ckd,
    r4_htn_hf,
    r5_htn_hf_ckd,
    r6_duplicate_hypertension,
    r7_diabetes_type,
    r9_ckd_stage,
    r10_heart_failure_type,
)
from app.rules.common import ckd_facts, diabetes_facts, heart_failure_facts, hypertension_facts
from tests.unit.rules.helpers import by_code, fact, inp, outcomes, run, sug


def test_index_synonyms_use_the_central_condition_family_classifier() -> None:
    facts = [
        fact("dm", "DM2", [1]),
        fact("htn", "high blood pressure", [2]),
        fact("ckd", "chronic renal failure stage 4", [3]),
        fact("hf", "left ventricular failure", [4]),
    ]
    rule_input = inp([], facts)

    assert [f.fact_id for f in diabetes_facts(rule_input)] == ["dm"]
    assert [f.fact_id for f in hypertension_facts(rule_input)] == ["htn"]
    assert [f.fact_id for f in ckd_facts(rule_input)] == ["ckd"]
    assert [f.fact_id for f in heart_failure_facts(rule_input)] == ["hf"]


@pytest.mark.parametrize(
    ("rule", "code", "right_fact", "other_fact", "rule_id"),
    [
        (
            r6_duplicate_hypertension.apply,
            "I10",
            fact("right", "hypertension", [1]),
            fact("other", "type 2 diabetes mellitus", [2]),
            "R6",
        ),
        (
            r7_diabetes_type.apply,
            "E11.9",
            fact("right", "type 2 diabetes mellitus", [1]),
            fact("other", "hypertension", [2]),
            "R7",
        ),
        (
            r9_ckd_stage.apply,
            "N18.4",
            fact("right", "chronic kidney disease stage 4", [1]),
            fact("other", "hypertension", [2]),
            "R9",
        ),
        (
            r10_heart_failure_type.apply,
            "I50.22",
            fact("right", "chronic systolic heart failure", [1]),
            fact("other", "hypertension", [2]),
            "R10",
        ),
    ],
)
def test_code_cannot_borrow_another_suggestions_condition_fact(
    rule: Rule,
    code: str,
    right_fact: ClinicalFact,
    other_fact: ClinicalFact,
    rule_id: str,
) -> None:
    out = run(rule, [sug("s1", code, ["other"])], [right_fact, other_fact])

    assert outcomes(by_code(out, code), rule_id) == ["fail"]


DM = fact("dm", "type 2 diabetes mellitus", [1])
HTN = fact("htn", "hypertension", [2])
CKD = fact("ckd", "chronic kidney disease stage 4", [3])
HF = fact("hf", "chronic diastolic heart failure", [4])


@pytest.mark.parametrize(
    ("rule", "rule_id", "code", "own", "facts"),
    [
        (r2_diabetes_ckd.apply, "R2", "E11.22", DM, [DM, CKD]),
        (r3_htn_ckd.apply, "R3", "I12.9", HTN, [HTN, CKD]),
        (r4_htn_hf.apply, "R4", "I11.0", HTN, [HTN, HF]),
        (r5_htn_hf_ckd.apply, "R5", "I13.0", HTN, [HTN, HF, CKD]),
    ],
)
def test_picked_combination_code_adopts_its_documented_parts(
    rule: Rule, rule_id: str, code: str, own: ClinicalFact, facts: list[ClinicalFact]
) -> None:
    # A selection names one fact, so the model's E11.22 can only cite the diabetes fact.
    out = run(rule, [sug("s1", code, [own.fact_id], own.evidence)], facts)

    picked = by_code(out, code)
    assert "fail" not in outcomes(picked, rule_id)
    assert picked.added_by_rule is None
    assert picked.fact_ids == sorted(f.fact_id for f in facts)
    assert picked.evidence == sorted(n for f in facts for n in f.evidence)


@pytest.mark.parametrize(
    ("rule", "rule_id", "code", "owner", "facts"),
    [
        # Owns only a part, not its own family: the code has no diabetes/hypertension fact.
        (r2_diabetes_ckd.apply, "R2", "E11.22", "ckd", [DM, CKD]),
        (r3_htn_ckd.apply, "R3", "I12.9", "ckd", [HTN, CKD]),
        # Owns its family but a part is not documented as an active fact.
        (r2_diabetes_ckd.apply, "R2", "E11.22", "dm", [DM]),
        (r5_htn_hf_ckd.apply, "R5", "I13.0", "htn", [HTN, CKD]),
    ],
)
def test_combination_code_without_its_own_family_or_a_documented_part_fails(
    rule: Rule, rule_id: str, code: str, owner: str, facts: list[ClinicalFact]
) -> None:
    out = run(rule, [sug("s1", code, [owner])], facts)

    assert "fail" in outcomes(by_code(out, code), rule_id)


def test_suspected_part_is_not_adopted() -> None:
    suspected_ckd = fact("ckd", "chronic kidney disease stage 4", [3], status="suspected")
    out = run(r2_diabetes_ckd.apply, [sug("s1", "E11.22", ["dm"])], [DM, suspected_ckd])

    assert outcomes(by_code(out, "E11.22"), "R2") == ["fail"]


def test_failed_unowned_code_is_not_removed_by_dedupe() -> None:
    htn_ckd = fact("right", "hypertension with chronic kidney disease stage 4", [1])
    other = fact("other", "type 2 diabetes mellitus", [2])
    out = run(
        r6_duplicate_hypertension.apply,
        [sug("s1", "I10", ["other"]), sug("s2", "I12.9", ["right"])],
        [htn_ckd, other],
    )

    assert outcomes(by_code(out, "I10"), "R6") == ["fail"]
