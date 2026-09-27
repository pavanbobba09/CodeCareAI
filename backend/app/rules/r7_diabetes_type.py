"""R7: diabetes type not documented -> E11 is the default; mark for review, no gap.

Source: ICD-10-CM Official Guidelines for Coding and Reporting FY2027, Section I.C.4.a.2
(Type of diabetes mellitus not documented: the default is E11.-, Type 2 diabetes mellitus).
Owner decision G (M3): the default is correct coding, so no gap is raised.
"""

import re

from app.models import RuleInput, RuleOutput
from app.rules.common import facts_by_id, not_suggested, result, with_result
from app.terminology.lookup import CodeLookup

RULE_ID = "R7"
SOURCE_REF = "ICD-10-CM Guidelines FY2027 §I.C.4.a.2"
TARGET_CODES: frozenset[str] = frozenset()
TYPED = re.compile(
    r"\btype\s*(1|2|i|ii|one|two)\b|\b(t[12]dm|dm[12]|iddm|niddm)\b"
    r"|gestational|secondary|due to|drug|chemical|neonatal|postpancreatectomy|postprocedural",
    re.IGNORECASE,
)


def apply(inp: RuleInput, codes: CodeLookup) -> RuleOutput:
    facts = facts_by_id(inp)
    out = []
    for s in inp.suggestions:
        diabetes = [
            facts[f]
            for f in s.fact_ids
            if f in facts and facts[f].kind == "condition" and "diabet" in facts[f].concept.lower()
        ]
        untyped = diabetes and all(
            not f.details.get("type") and not TYPED.search(f.concept) for f in diabetes
        )
        if s.code.startswith("E11") and untyped and not not_suggested(s):
            s = with_result(
                s,
                result(
                    RULE_ID,
                    "needs_review",
                    "Diabetes type is not documented; E11 (type 2) is the guideline default.",
                    SOURCE_REF,
                    [s.code],
                ),
            )
        out.append(s)
    return RuleOutput(suggestions=out, dropped=[], gaps=[])
