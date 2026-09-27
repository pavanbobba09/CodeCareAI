"""R7: diabetes type not documented -> E11 is the default; mark for review, no gap.

Source: ICD-10-CM Official Guidelines for Coding and Reporting FY2027, Section I.C.4.a.2
(Type of diabetes mellitus not documented: the default is E11.-, Type 2 diabetes mellitus).
Owner decision G (M3): the default is correct coding, so no gap is raised.

A selected E10 (type 1) or E13 (other specified) code whose diabetes facts document no type
is replaced by the E11 code with the same suffix (E10.9 -> E11.9), marked for review.

Any diabetes code (E08-E13) with no active diabetes fact (for example only "history of
diabetes", or a code attached to another fact) is kept as not suggested.
"""

import re

from app.models import DroppedCode, RuleInput, RuleOutput, Suggestion
from app.rules.common import (
    added,
    diabetes_facts,
    facts_by_id,
    is_diabetes,
    not_suggested,
    present,
    result,
    with_result,
)
from app.terminology.lookup import CodeLookup

RULE_ID = "R7"
SOURCE_REF = "ICD-10-CM Guidelines FY2027 §I.C.4.a.2"
TARGET_CODES: frozenset[str] = frozenset()
TYPED = re.compile(
    r"\btype\s*(1|2|i|ii|one|two)\b|\b(t[12]dm|dm[12]|iddm|niddm)\b"
    r"|gestational|secondary|due to|drug|chemical|neonatal|postpancreatectomy|postprocedural",
    re.IGNORECASE,
)


def counterpart(code: str) -> str | None:
    """The E11 code with the same suffix, for an E10 or E13 code."""
    return f"E11{code[3:]}" if code[:3] in {"E10", "E13"} else None


def _untyped(inp: RuleInput, s: Suggestion) -> bool:
    by_id = facts_by_id(inp)
    diabetes = [f for f in diabetes_facts(inp) if f.fact_id in s.fact_ids] or [
        by_id[f] for f in s.fact_ids if f in by_id and "diabet" in by_id[f].concept.lower()
    ]
    return bool(diabetes) and all(
        not f.details.get("type") and not TYPED.search(f.concept) for f in diabetes
    )


def apply(inp: RuleInput, codes: CodeLookup) -> RuleOutput:
    review = result(
        RULE_ID,
        "needs_review",
        "Diabetes type is not documented; E11 (type 2) is the guideline default.",
        SOURCE_REF,
        [],
    )
    documented = bool(diabetes_facts(inp))
    out: list[Suggestion] = []
    dropped: list[DroppedCode] = []
    for s in inp.suggestions:
        if not documented and is_diabetes(s.code) and not not_suggested(s):
            r = result(
                RULE_ID,
                "fail",
                f"{s.code} needs documented active diabetes.",
                SOURCE_REF,
                [s.code],
            )
            out.append(with_result(s, r))
            continue
        if not_suggested(s) or not _untyped(inp, s):
            out.append(s)
            continue
        e11 = counterpart(s.code)
        if e11 is not None and codes.get_code(e11, inp.code_sets.icd10cm) is not None:
            dropped.append(
                DroppedCode(
                    code=s.code,
                    fact_ids=s.fact_ids,
                    rule_id=RULE_ID,
                    reason=f"Diabetes type is not documented; {e11} is the default.",
                )
            )
            if present(out, e11) or present(inp.suggestions, e11):
                continue
            r = review.model_copy(update={"affects_codes": [e11]})
            out.append(added(inp, codes, e11, RULE_ID, [s], r, s.fact_ids))
        elif s.code.startswith("E11"):
            out.append(with_result(s, review.model_copy(update={"affects_codes": [s.code]})))
        else:
            out.append(s)
    return RuleOutput(suggestions=out, dropped=dropped, gaps=[])
