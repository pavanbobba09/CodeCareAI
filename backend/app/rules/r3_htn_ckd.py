"""R3: hypertension with CKD -> I12.9 or I12.0 plus N18.x.

Source: ICD-10-CM Official Guidelines for Coding and Reporting FY2027, Section I.C.9.a.2
(Hypertensive Chronic Kidney Disease: assign I12 when both hypertension and N18 CKD are
present; CKD is not coded as hypertensive if the provider indicates it is not related; add
the N18 code for the stage). I12.0 = stage 5 CKD or ESRD; I12.9 = stage 1-4 or unspecified
(Tabular). Skipped when R5 (I13) applies.

Both conditions must be documented by active facts; the variant and the added N18 code
follow the stage the CKD facts document (n007: stage 5 -> I12.0 + N18.5), never a selected
code, and exactly one of I12.0/I12.9 is left. A selected I12 without both conditions
documented is kept as not suggested. When the note links the CKD `caused_by` something
other than the hypertension, the link is not presumed and the codes are marked for review.
"""

from app.models import DroppedCode, RuleInput, RuleOutput
from app.rules.common import (
    N18_CODES,
    Conditions,
    active,
    fail_all,
    ids_of,
    is_ckd,
    is_hypertension,
    owns_families,
    result,
    review_all,
    settle_variant,
    stage5_or_esrd,
    stage_additions,
)
from app.terminology.lookup import CodeLookup

RULE_ID = "R3"
SOURCE_REF = "ICD-10-CM Guidelines FY2027 §I.C.9.a.2; Tabular I12 use additional code"
TARGET_CODES = frozenset({"I12.0", "I12.9", *N18_CODES})
VARIANTS = {"I12.0", "I12.9"}


def apply(inp: RuleInput, codes: CodeLookup) -> RuleOutput:
    out = list(inp.suggestions)
    dropped: list[DroppedCode] = []
    htn_codes = [s for s in active(out) if is_hypertension(s.code)]
    if not htn_codes or any(s.code.startswith("I13") for s in htn_codes):
        return RuleOutput(suggestions=out, dropped=dropped, gaps=[])
    c = Conditions(inp)
    i12 = [s for s in htn_codes if s.code.startswith("I12")]
    unowned = [s for s in i12 if not owns_families(inp, s, "hypertension", "ckd")]
    if unowned:
        r = result(
            RULE_ID,
            "fail",
            "I12 needs its own active hypertension and CKD facts.",
            SOURCE_REF,
            [s.code for s in unowned],
        )
        out = fail_all(out, unowned, r)
        htn_codes = [s for s in active(out) if is_hypertension(s.code)]
        i12 = [s for s in htn_codes if s.code.startswith("I12")]
        if not htn_codes:
            return RuleOutput(suggestions=out, dropped=dropped, gaps=[])
    if not (c.htn and c.ckd):
        if i12:
            r = result(
                RULE_ID,
                "fail",
                "I12 needs documented hypertension and CKD; the note does not document both.",
                SOURCE_REF,
                [s.code for s in i12],
            )
            out = fail_all(out, i12, r)
        return RuleOutput(suggestions=out, dropped=dropped, gaps=[])
    target = "I12.0" if stage5_or_esrd(c.ckd) else "I12.9"
    if not c.ckd_linked:
        r = result(
            RULE_ID,
            "needs_review",
            "The note links the CKD to another cause, so the hypertension link is not "
            f"presumed; check whether {target} applies.",
            SOURCE_REF,
            [s.code for s in htn_codes],
        )
        ckd_codes = [s for s in active(out) if is_ckd(s.code)]
        return RuleOutput(
            suggestions=review_all(out, htn_codes + ckd_codes, r), dropped=dropped, gaps=[]
        )
    r = result(
        RULE_ID,
        "pass",
        f"Hypertension with CKD: {target} with the N18 stage code.",
        SOURCE_REF,
        [target],
    )
    ids = ids_of([*c.htn, *c.ckd])
    out, dropped = settle_variant(inp, codes, out, VARIANTS, target, RULE_ID, r, ids)
    out += stage_additions(inp.model_copy(update={"suggestions": out}), codes, RULE_ID, r, c.ckd)
    return RuleOutput(suggestions=out, dropped=dropped, gaps=[])
