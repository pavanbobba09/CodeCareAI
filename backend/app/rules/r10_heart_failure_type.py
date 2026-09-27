"""R10: heart failure type or acuity missing -> keep the supported code, raise a gap.

Sources: ICD-10-CM Official Guidelines for Coding and Reporting FY2027, Sections I.C.9.a.1
and I.C.9.a.3 (assign an additional code from category I50 to identify the type of heart
failure). Acuity has no guideline sentence of its own; it is the I50.2-/I50.3-/I50.4-
subcode axis (acute, chronic, acute on chronic) in the Tabular List.
"""

from app.models import Gap, RuleInput, RuleOutput, Suggestion
from app.rules.common import active, is_heart_failure, result, with_result
from app.terminology.lookup import CodeLookup

RULE_ID = "R10"
SOURCE_REF = "ICD-10-CM Guidelines FY2027 §I.C.9.a.1, §I.C.9.a.3; Tabular I50.2-I50.4"
TARGET_CODES: frozenset[str] = frozenset()

# Neutral wording: ask for the missing fact, never for a code or a preferred answer.
MISSING = {
    "I50.9": (
        "heart failure type",
        "The note documents heart failure without a type. Please document the type, if known.",
    ),
    **{
        code: (
            "heart failure acuity",
            f"The note documents {kind} heart failure without acuity. "
            "Please document whether it is acute, chronic, or acute on chronic, if known.",
        )
        for code, kind in [
            ("I50.20", "systolic"),
            ("I50.30", "diastolic"),
            ("I50.40", "combined systolic and diastolic"),
        ]
    },
}


def apply(inp: RuleInput, codes: CodeLookup) -> RuleOutput:
    live = {s.suggestion_id for s in active(inp.suggestions)}
    out: list[Suggestion] = []
    gaps: list[Gap] = []
    for s in inp.suggestions:
        if s.suggestion_id not in live or not is_heart_failure(s.code):
            out.append(s)
            continue
        if s.code in MISSING:
            missing, query = MISSING[s.code]
            gap = Gap(
                gap_id=f"{RULE_ID}-{s.code}",
                kind="missing",
                missing=missing,
                affects_codes=[s.code],
                rule_id=RULE_ID,
                query_text=query,
                severity="review",
            )
            gaps.append(gap)
            r = result(RULE_ID, "needs_review", f"Missing: {missing}.", SOURCE_REF, [s.code])
            out.append(with_result(s, r, gap))
        else:
            r = result(
                RULE_ID,
                "pass",
                f"{s.code} states heart failure type and acuity.",
                SOURCE_REF,
                [s.code],
            )
            out.append(with_result(s, r))
    return RuleOutput(suggestions=out, dropped=[], gaps=gaps)
