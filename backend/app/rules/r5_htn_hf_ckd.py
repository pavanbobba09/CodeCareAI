"""R5: hypertension with heart failure and CKD -> I13.0 or I13.2, plus I50.x and N18.x.

Source: ICD-10-CM Official Guidelines for Coding and Reporting FY2027, Section I.C.9.a.3
(Hypertensive Heart and Chronic Kidney Disease: assign I13 when there is hypertension with
both heart and chronic kidney disease; add I50 for the type of heart failure and N18 for the
stage). I13.0 = heart failure with stage 1-4 or unspecified CKD; I13.2 = heart failure with
stage 5 CKD or ESRD (Tabular). Runs before R4 and R3.

All three conditions must be documented by active facts. The variant follows the stage the
CKD facts document, never a selected code; exactly one of I13.0/I13.10/I13.11/I13.2 is left.
A selected I13 code without its conditions documented is kept as not suggested.
"""

from app.models import DroppedCode, RuleInput, RuleOutput
from app.rules.common import (
    N18_CODES,
    Conditions,
    active,
    fail_all,
    ids_of,
    is_hypertension,
    result,
    review_all,
    settle_variant,
    stage5_or_esrd,
    stage_additions,
)
from app.terminology.lookup import CodeLookup

RULE_ID = "R5"
SOURCE_REF = "ICD-10-CM Guidelines FY2027 §I.C.9.a.3; Tabular I13 use additional code"
TARGET_CODES = frozenset({"I13.0", "I13.2", *N18_CODES})
VARIANTS = {"I13.0", "I13.10", "I13.11", "I13.2"}


def apply(inp: RuleInput, codes: CodeLookup) -> RuleOutput:
    out = list(inp.suggestions)
    dropped: list[DroppedCode] = []
    htn_codes = [s for s in active(out) if is_hypertension(s.code)]
    if not htn_codes:
        return RuleOutput(suggestions=out, dropped=dropped, gaps=[])
    c = Conditions(inp)
    i13 = [s for s in htn_codes if s.code.startswith("I13")]
    if not (c.htn and c.hf and c.ckd):
        if i13:
            r = result(
                RULE_ID,
                "fail",
                "I13 needs documented hypertension, heart failure and CKD; the note does "
                "not document all three.",
                SOURCE_REF,
                [s.code for s in i13],
            )
            out = fail_all(out, i13, r)
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
    return RuleOutput(suggestions=out, dropped=dropped, gaps=[])
