"""R3: hypertension with CKD -> I12.9 or I12.0 plus N18.x.

Source: ICD-10-CM Official Guidelines for Coding and Reporting FY2027, Section I.C.9.a.2
(Hypertensive Chronic Kidney Disease: assign I12 when both hypertension and N18 CKD are
present; CKD is not coded as hypertensive if the provider indicates it is not related; add
the N18 code for the stage). I12.0 = stage 5 CKD or ESRD; I12.9 = stage 1-4 or unspecified
(Tabular). Skipped when R5 (I13) applies.

When the note links the CKD `caused_by` something other than the hypertension, the link is
not presumed and the codes are marked for review. I12 says "use additional code to identify
the stage": when no N18 code was selected, the documented stage is added (n007: I12.0 with
stage 5 -> N18.5).
"""

from app.models import RuleInput, RuleOutput
from app.rules.common import (
    N18_CODES,
    Hypertension,
    added,
    fact_ids,
    present,
    result,
    review_all,
    stage_additions,
)
from app.terminology.lookup import CodeLookup

RULE_ID = "R3"
SOURCE_REF = "ICD-10-CM Guidelines FY2027 §I.C.9.a.2; Tabular I12 use additional code"
TARGET_CODES = frozenset({"I12.0", "I12.9", *N18_CODES})


def apply(inp: RuleInput, codes: CodeLookup) -> RuleOutput:
    h = Hypertension(inp)
    out = list(inp.suggestions)
    if not (h.htn and h.has_ckd) or h.has_i13:
        return RuleOutput(suggestions=out, dropped=[], gaps=[])
    target = "I12.0" if h.stage5_or_esrd() else "I12.9"
    if not h.ckd_linked:
        r = result(
            RULE_ID,
            "needs_review",
            "The note links the CKD to another cause, so the hypertension link is not "
            f"presumed; check whether {target} applies.",
            SOURCE_REF,
            [s.code for s in h.htn + h.ckd],
        )
        return RuleOutput(suggestions=review_all(out, h.htn + h.ckd, r), dropped=[], gaps=[])
    r = result(
        RULE_ID,
        "pass",
        f"Hypertension with CKD: {target} with the N18 stage code.",
        SOURCE_REF,
        [target],
    )
    if not any(s.code.startswith("I12") for s in h.htn) and not present(out, target):
        ids = sorted({*fact_ids(h.htn), *h.ckd_ids})
        out.append(added(inp, codes, target, RULE_ID, h.htn + h.ckd, r, ids))
    staged = inp.model_copy(update={"suggestions": out})
    out += stage_additions(staged, codes, RULE_ID, r, h.ckd_facts)
    return RuleOutput(suggestions=out, dropped=[], gaps=[])
