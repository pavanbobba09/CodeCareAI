"""R6: remove I10 when a hypertensive combination code applies; I13 replaces I11 and I12.

Sources: ICD-10-CM Official Guidelines for Coding and Reporting FY2027, Section I.C.9.a.1
(I10 is assigned with heart failure only when the provider documents them as unrelated) and
I.C.9.a.3 ("If a patient has hypertension, heart disease and chronic kidney disease, then a
code from I13 should be used, not codes from I11 or I12"). I11, I12 and I13 include the
hypertension, so I10 alongside them reports it twice.

Any hypertension code (I10-I13) with no active hypertension fact (for example only "history
of hypertension", or a code attached to another fact) is kept as not suggested. R3-R5 do
the same for their own combination codes; this also covers I10.
"""

from app.models import DroppedCode, RuleInput, RuleOutput
from app.rules.common import (
    active,
    fail_all,
    is_hypertension,
    not_suggested,
    owns_families,
    result,
)
from app.terminology.lookup import CodeLookup

RULE_ID = "R6"
SOURCE_REF = "ICD-10-CM Guidelines FY2027 §I.C.9.a.1, §I.C.9.a.3"
TARGET_CODES: frozenset[str] = frozenset()


def apply(inp: RuleInput, codes: CodeLookup) -> RuleOutput:
    undocumented = [
        s
        for s in active(inp.suggestions)
        if is_hypertension(s.code) and not owns_families(inp, s, "hypertension")
    ]
    suggestions = list(inp.suggestions)
    if undocumented:
        r = result(
            RULE_ID,
            "fail",
            "Hypertension codes need their own active hypertension fact.",
            SOURCE_REF,
            [s.code for s in undocumented],
        )
        suggestions = fail_all(suggestions, undocumented, r)
    categories = {s.code[:3] for s in active(suggestions) if is_hypertension(s.code)}
    if "I13" in categories:
        covered = {"I10", "I11", "I12"}
        why = "I13 includes the hypertension, heart disease and CKD"
    elif categories & {"I11", "I12"}:
        covered = {"I10"}
        why = "the hypertensive combination code includes the hypertension"
    else:
        return RuleOutput(suggestions=suggestions, dropped=[], gaps=[])
    kept, dropped = [], []
    for s in suggestions:
        if s.code[:3] in covered and not not_suggested(s):
            dropped.append(
                DroppedCode(
                    code=s.code, fact_ids=s.fact_ids, rule_id=RULE_ID, reason=f"Removed: {why}."
                )
            )
        else:
            kept.append(s)
    return RuleOutput(suggestions=kept, dropped=dropped, gaps=[])
