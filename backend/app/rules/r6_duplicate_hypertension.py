"""R6: remove I10 when a hypertensive combination code applies; I13 replaces I11 and I12.

Sources: ICD-10-CM Official Guidelines for Coding and Reporting FY2027, Section I.C.9.a.1
(I10 is assigned with heart failure only when the provider documents them as unrelated) and
I.C.9.a.3 ("If a patient has hypertension, heart disease and chronic kidney disease, then a
code from I13 should be used, not codes from I11 or I12"). I11, I12 and I13 include the
hypertension, so I10 alongside them reports it twice.
"""

from app.models import DroppedCode, RuleInput, RuleOutput
from app.rules.common import active, is_hypertension
from app.terminology.lookup import CodeLookup

RULE_ID = "R6"
SOURCE_REF = "ICD-10-CM Guidelines FY2027 §I.C.9.a.1, §I.C.9.a.3"
TARGET_CODES: frozenset[str] = frozenset()


def apply(inp: RuleInput, codes: CodeLookup) -> RuleOutput:
    categories = {s.code[:3] for s in active(inp.suggestions) if is_hypertension(s.code)}
    if "I13" in categories:
        covered = {"I10", "I11", "I12"}
        why = "I13 includes the hypertension, heart disease and CKD"
    elif categories & {"I11", "I12"}:
        covered = {"I10"}
        why = "the hypertensive combination code includes the hypertension"
    else:
        return RuleOutput(suggestions=inp.suggestions, dropped=[], gaps=[])
    kept, dropped = [], []
    for s in inp.suggestions:
        if s.code[:3] in covered:
            dropped.append(
                DroppedCode(
                    code=s.code, fact_ids=s.fact_ids, rule_id=RULE_ID, reason=f"Removed: {why}."
                )
            )
        else:
            kept.append(s)
    return RuleOutput(suggestions=kept, dropped=dropped, gaps=[])
