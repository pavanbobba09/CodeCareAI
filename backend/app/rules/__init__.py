"""Deterministic coding rules R1-R14 (DESIGN.md §3.4), one module per rule.

Every rule is pure: apply(inp: RuleInput, codes: CodeLookup) -> RuleOutput.
No LLM calls and no db calls inside a rule.
"""

from collections.abc import Callable

from app.models import DroppedCode, Gap, RuleInput, RuleOutput, Suggestion
from app.rules import (
    r1_code_validity,
    r2_diabetes_ckd,
    r3_htn_ckd,
    r4_htn_hf,
    r5_htn_hf_ckd,
    r6_duplicate_hypertension,
    r7_diabetes_type,
    r8_diabetes_drugs,
    r9_ckd_stage,
    r10_heart_failure_type,
    r11_uncertain_diagnosis,
    r12_excludes1,
)
from app.terminology.lookup import CodeLookup

Rule = Callable[[RuleInput, CodeLookup], RuleOutput]

# Order matters: each rule sees the previous rule's kept suggestions.
# R11 first, so combination rules only combine codes that can be reported. R1 runs on the
# LLM's picks, then again last on the codes R2-R8 added. R5 before R4 and R3 (I13 wins).
ICD_RULES: list[Rule] = [
    r11_uncertain_diagnosis.apply,
    r1_code_validity.apply,
    r2_diabetes_ckd.apply,
    r5_htn_hf_ckd.apply,
    r4_htn_hf.apply,
    r3_htn_ckd.apply,
    r6_duplicate_hypertension.apply,
    r7_diabetes_type.apply,
    r8_diabetes_drugs.apply,
    r9_ckd_stage.apply,
    r10_heart_failure_type.apply,
    r12_excludes1.apply,
    r1_code_validity.apply,
]
# Skipped when CodeSetSelection.cpt is None (DESIGN.md §3.4). R13 and R14 arrive in M6.
CPT_RULES: list[Rule] = []

# Codes rules may add; run_rules preloads them so rules never touch the db.
TARGET_CODES: frozenset[str] = frozenset().union(
    r2_diabetes_ckd.TARGET_CODES,
    r3_htn_ckd.TARGET_CODES,
    r4_htn_hf.TARGET_CODES,
    r5_htn_hf_ckd.TARGET_CODES,
    r8_diabetes_drugs.TARGET_CODES,
)


def codes_to_preload(selected: set[str]) -> set[str]:
    """ICD-10-CM codes a note's rules may need: every rule target, plus the E11 counterparts
    R7 may put in place of an untyped E10/E13 code."""
    counterparts = {c for code in selected if (c := r7_diabetes_type.counterpart(code))}
    return {*TARGET_CODES, *counterparts}


def _number_new(suggestions: list[Suggestion]) -> list[Suggestion]:
    """Give suggestions added by a rule the next free id (s1..sn are the LLM's picks)."""
    used = [int(s.suggestion_id[1:]) for s in suggestions if s.suggestion_id]
    next_id = max(used, default=0) + 1
    out = []
    for s in suggestions:
        if not s.suggestion_id:
            s = s.model_copy(update={"suggestion_id": f"s{next_id}"})
            next_id += 1
        out.append(s)
    return out


def run_all(inp: RuleInput, codes: CodeLookup) -> RuleOutput:
    rules = ICD_RULES + (CPT_RULES if inp.code_sets.cpt is not None else [])
    suggestions = inp.suggestions
    dropped: list[DroppedCode] = []
    gaps: list[Gap] = []
    for rule in rules:
        out = rule(inp.model_copy(update={"suggestions": suggestions}), codes)
        suggestions = _number_new(out.suggestions)
        dropped += out.dropped
        gaps += out.gaps
    # A gap on a code a later rule removed no longer applies.
    live_gaps = {g for s in suggestions for g in s.gap_ids}
    gaps = [g for g in gaps if g.gap_id in live_gaps]
    return RuleOutput(suggestions=suggestions, dropped=dropped, gaps=gaps)
