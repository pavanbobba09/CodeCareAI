import pytest

from app.models import ClinicalFact
from app.rules import (
    Rule,
    r2_diabetes_ckd,
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


def test_combination_code_owns_every_condition_family() -> None:
    dm = fact("dm", "type 2 diabetes mellitus", [1])
    ckd = fact("ckd", "chronic kidney disease stage 4", [2])
    out = run(r2_diabetes_ckd.apply, [sug("s1", "E11.22", ["dm"])], [dm, ckd])

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
