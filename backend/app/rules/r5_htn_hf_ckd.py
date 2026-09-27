"""R5: hypertension with heart failure and CKD -> I13.0 or I13.2, plus I50.x and N18.x.

Source: ICD-10-CM Official Guidelines for Coding and Reporting FY2027, Section I.C.9.a.3
(Hypertensive Heart and Chronic Kidney Disease: assign I13 when there is hypertension with
both heart and chronic kidney disease; add I50 for the type of heart failure and N18 for the
stage). I13.0 = heart failure with stage 1-4 or unspecified CKD; I13.2 = heart failure with
stage 5 CKD or ESRD (Tabular). Runs before R4 and R3. I13 says "use additional code to
identify the stage": when no N18 code was selected, the documented stage is added.
"""

from app.models import RuleInput, RuleOutput
from app.rules.common import (
    N18_CODES,
    Hypertension,
    added,
    fact_ids,
    present,
    result,
    stage_additions,
)
from app.terminology.lookup import CodeLookup

RULE_ID = "R5"
SOURCE_REF = "ICD-10-CM Guidelines FY2027 §I.C.9.a.3; Tabular I13 use additional code"
TARGET_CODES = frozenset({"I13.0", "I13.2", *N18_CODES})


def apply(inp: RuleInput, codes: CodeLookup) -> RuleOutput:
    h = Hypertension(inp)
    out = list(inp.suggestions)
    if not (h.hf_linked and h.ckd_linked):
        return RuleOutput(suggestions=out, dropped=[], gaps=[])
    target = "I13.2" if h.stage5_or_esrd() else "I13.0"
    r = result(
        RULE_ID,
        "pass",
        f"Hypertension with heart failure and CKD: {target} with the I50 and N18 codes.",
        SOURCE_REF,
        [target],
    )
    if not h.has_i13 and not present(out, target):
        ids = sorted({*fact_ids(h.htn + h.hf), *h.ckd_ids})
        out.append(added(inp, codes, target, RULE_ID, h.htn + h.hf + h.ckd, r, ids))
    staged = inp.model_copy(update={"suggestions": out})
    out += stage_additions(staged, codes, RULE_ID, r, h.ckd_facts)
    return RuleOutput(suggestions=out, dropped=[], gaps=[])
