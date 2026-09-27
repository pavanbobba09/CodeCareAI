"""R7: reconcile the selected diabetes family with the documented type.

Source: ICD-10-CM Official Guidelines for Coding and Reporting FY2027, Section I.C.4.a.2
(Type of diabetes mellitus not documented: the default is E11.-, Type 2 diabetes mellitus).
Owner decision G (M3): the default is correct coding, so no gap is raised.

A documented type 1 fact uses E10 and a documented type 2 fact uses E11. When the facts
document no type, E11 is the default; an E10/E13 selection becomes its E11 counterpart and
is marked for review without a gap.

Any diabetes code (E08-E13) without its own active diabetes fact (for example only "history
of diabetes", or a code attached to another fact) is kept as not suggested.
"""

import re

from app.models import ClinicalFact, DroppedCode, RuleInput, RuleOutput, Suggestion
from app.rules.common import (
    active,
    added,
    is_diabetes,
    not_suggested,
    own_family_facts,
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


def counterparts(code: str) -> set[str]:
    """Type 1 and type 2 variants R7 may need for a selected diabetes code."""
    if not is_diabetes(code):
        return set()
    return {f"E10{code[3:]}", f"E11{code[3:]}"}


def _type(facts: list[ClinicalFact]) -> str | None:
    found: set[str] = set()
    for raw in facts:
        concept = raw.concept.lower()
        detail = raw.details.get("type", "").lower()
        text = f"{concept} {detail}"
        type1 = detail in {"1", "i", "one", "type 1"} or bool(re.search(
            r"\btype\s*(1|i|one)\b|\bt1dm\b|\bdm1\b|\biddm\b", text
        ))
        type2 = detail in {"2", "ii", "two", "type 2"} or bool(re.search(
            r"\btype\s*(2|ii|two)\b|\bt2dm\b|\bdm2\b|\bniddm\b", text
        ))
        if type1:
            found.add("1")
        if type2:
            found.add("2")
        if TYPED.search(text) and not (type1 or type2):
            found.add("other")
    return next(iter(found)) if len(found) == 1 else None


def apply(inp: RuleInput, codes: CodeLookup) -> RuleOutput:
    review = result(
        RULE_ID,
        "needs_review",
        "Diabetes type is not documented; E11 (type 2) is the guideline default.",
        SOURCE_REF,
        [],
    )
    out: list[Suggestion] = []
    dropped: list[DroppedCode] = []
    for s in inp.suggestions:
        if is_diabetes(s.code) and present(active(out), s.code):
            continue
        own = own_family_facts(inp, s, "diabetes") if is_diabetes(s.code) else []
        if is_diabetes(s.code) and not own and not not_suggested(s):
            r = result(
                RULE_ID,
                "fail",
                f"{s.code} needs its own active diabetes fact.",
                SOURCE_REF,
                [s.code],
            )
            out.append(with_result(s, r))
            continue
        if not_suggested(s) or not is_diabetes(s.code):
            out.append(s)
            continue
        documented_type = _type(own)
        target_prefix = (
            "E10"
            if documented_type == "1"
            else "E11"
            if documented_type in {None, "2"}
            else s.code[:3]
        )
        target = f"{target_prefix}{s.code[3:]}"
        if target != s.code and codes.get_code(target, inp.code_sets.icd10cm) is not None:
            dropped.append(
                DroppedCode(
                    code=s.code,
                    fact_ids=s.fact_ids,
                    rule_id=RULE_ID,
                    reason=(
                        f"The documented diabetes type calls for {target}, not {s.code}."
                        if documented_type is not None
                        else f"Diabetes type is not documented; {target} is the default."
                    ),
                )
            )
            if present(active(out), target):
                continue
            r = (
                review.model_copy(update={"affects_codes": [target]})
                if documented_type is None
                else result(
                    RULE_ID,
                    "pass",
                    f"{target} matches the documented diabetes type.",
                    SOURCE_REF,
                    [target],
                )
            )
            out.append(added(inp, codes, target, RULE_ID, [s], r, [f.fact_id for f in own]))
        elif documented_type is None and s.code.startswith("E11"):
            out.append(with_result(s, review.model_copy(update={"affects_codes": [s.code]})))
        else:
            out.append(s)
    return RuleOutput(suggestions=out, dropped=dropped, gaps=[])
