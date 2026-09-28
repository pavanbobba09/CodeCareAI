"""R5: hypertension with heart failure and CKD -> I13.0 or I13.2, plus I50.x and N18.x.

Source: ICD-10-CM Official Guidelines for Coding and Reporting FY2027, Section I.C.9.a.3
(Hypertensive Heart and Chronic Kidney Disease: assign I13 when there is hypertension with
both heart and chronic kidney disease; add I50 for the type of heart failure and N18 for the
stage). I13.0 = heart failure with stage 1-4 or unspecified CKD; I13.2 = heart failure with
stage 5 CKD or ESRD (Tabular). Runs before R4 and R3.

When heart failure is documented, all three conditions must have active facts. The variant
follows the CKD stage, never a selected code; exactly one of
I13.0/I13.10/I13.11/I13.2 is left. I13.10/I13.11 do not themselves assert heart failure,
so they require owned hypertension and CKD facts but no HF fact. A selected I13 code
without the conditions it asserts is kept as not suggested.
"""

from app.models import DroppedCode, RuleInput, RuleOutput
from app.rules.common import (
    HF_CODES,
    N18_CODES,
    Conditions,
    active,
    adopt_documented_parts,
    code_condition_families,
    fail_all,
    heart_failure_additions,
    ids_of,
    is_hypertension,
    owns_families,
    result,
    review_all,
    settle_variant,
    stage5_or_esrd,
    stage_additions,
)
from app.terminology.lookup import CodeLookup

RULE_ID = "R5"
SOURCE_REF = "ICD-10-CM Guidelines FY2027 §I.C.9.a.3; Tabular I13 use additional code"
TARGET_CODES = frozenset({"I13.0", "I13.2", *N18_CODES, *HF_CODES})
VARIANTS = {"I13.0", "I13.10", "I13.11", "I13.2"}


def apply(inp: RuleInput, codes: CodeLookup) -> RuleOutput:
    out = list(inp.suggestions)
    dropped: list[DroppedCode] = []
    htn_codes = [s for s in active(out) if is_hypertension(s.code)]
    if not htn_codes:
        return RuleOutput(suggestions=out, dropped=dropped, gaps=[])
    c = Conditions(inp)
    out = adopt_documented_parts(
        inp, out, [s for s in htn_codes if s.code.startswith("I13")], "hypertension"
    )
    htn_codes = [s for s in active(out) if is_hypertension(s.code)]
    i13 = [s for s in htn_codes if s.code.startswith("I13")]
    unowned = [s for s in i13 if not owns_families(inp, s, *code_condition_families(s.code))]
    if unowned:
        r = result(
            RULE_ID,
            "fail",
            "I13 needs its own active facts for every condition it asserts.",
            SOURCE_REF,
            [s.code for s in unowned],
        )
        out = fail_all(out, unowned, r)
        htn_codes = [s for s in active(out) if is_hypertension(s.code)]
        i13 = [s for s in htn_codes if s.code.startswith("I13")]
        if not htn_codes:
            return RuleOutput(suggestions=out, dropped=dropped, gaps=[])
    if not (c.htn and c.hf and c.ckd):
        i13_with_hf = [s for s in i13 if "heart_failure" in code_condition_families(s.code)]
        if i13_with_hf:
            r = result(
                RULE_ID,
                "fail",
                "I13 needs documented hypertension, heart failure and CKD; the note does "
                "not document all three.",
                SOURCE_REF,
                [s.code for s in i13_with_hf],
            )
            out = fail_all(out, i13_with_hf, r)
        return RuleOutput(suggestions=out, dropped=dropped, gaps=[])
    if not (c.hf_linked and c.ckd_linked):
        if i13:  # R4/R3 skip while an I13 code is live, so flag it here
            r = result(
                RULE_ID,
                "needs_review",
                "The note links the heart failure or CKD to another cause, so the "
                "hypertension link is not presumed; check whether I13 applies.",
                SOURCE_REF,
                [s.code for s in i13],
            )
            out = review_all(out, i13, r)
        return RuleOutput(suggestions=out, dropped=dropped, gaps=[])
    target = "I13.2" if stage5_or_esrd(c.ckd) else "I13.0"
    r = result(
        RULE_ID,
        "pass",
        f"Hypertension with heart failure and CKD: {target} with the I50 and N18 codes.",
        SOURCE_REF,
        [target],
    )
    ids = ids_of([*c.htn, *c.hf, *c.ckd])
    out, dropped = settle_variant(inp, codes, out, VARIANTS, target, RULE_ID, r, ids)
    out += stage_additions(inp.model_copy(update={"suggestions": out}), codes, RULE_ID, r, c.ckd)
    out += heart_failure_additions(
        inp.model_copy(update={"suggestions": out}), codes, RULE_ID, r, c.hf
    )
    return RuleOutput(suggestions=out, dropped=dropped, gaps=[])
