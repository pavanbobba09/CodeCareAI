"""R10: reconcile I50 with documented heart-failure type and acuity.

Sources: ICD-10-CM Official Guidelines for Coding and Reporting FY2027, Sections I.C.9.a.1
and I.C.9.a.3 (assign an additional code from category I50 to identify the type of heart
failure). Acuity has no guideline sentence of its own; it is the I50.2-/I50.3-/I50.4-
subcode axis (acute, chronic, acute on chronic) in the Tabular List.

The code is normalized in both directions: the documented type and acuity may make it more
or less specific. Missing type becomes I50.9; documented type without acuity becomes
I50.20/I50.30/I50.40, with a neutral gap. An I50 code without its own active heart-failure
fact is kept as not suggested.
"""

from app.models import DroppedCode, Gap, RuleInput, RuleOutput, Suggestion
from app.rules.common import (
    HF_CODES,
    active,
    added,
    documented_heart_failure_code,
    documented_heart_failure_codes,
    is_heart_failure,
    own_family_facts,
    present,
    result,
    with_result,
)
from app.terminology.lookup import CodeLookup

RULE_ID = "R10"
SOURCE_REF = "ICD-10-CM Guidelines FY2027 §I.C.9.a.1, §I.C.9.a.3; Tabular I50.2-I50.4"
TARGET_CODES = HF_CODES

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
    dropped: list[DroppedCode] = []
    gaps: list[Gap] = []
    for s in inp.suggestions:
        if s.suggestion_id not in live or not is_heart_failure(s.code):
            out.append(s)
            continue
        if present(active(out), s.code):
            continue
        if any(r.rule_id == RULE_ID for r in s.rule_results):
            out.append(s)
            continue
        own = own_family_facts(inp, s, "heart_failure")
        if not own:
            r = result(
                RULE_ID,
                "fail",
                f"{s.code} needs its own active heart failure fact.",
                SOURCE_REF,
                [s.code],
            )
            out.append(with_result(s, r))
            continue
        documented = documented_heart_failure_codes(own)
        target = documented[0] if len(documented) == 1 else s.code
        if target != s.code:
            dropped.append(
                DroppedCode(
                    code=s.code,
                    fact_ids=s.fact_ids,
                    rule_id=RULE_ID,
                    reason=f"The note documents {target}, not {s.code}.",
                )
            )
            if present(active(out), target):
                continue
            placeholder = result(RULE_ID, "pass", "", SOURCE_REF, [target])
            supporting = [f.fact_id for f in own if documented_heart_failure_code(f) == target]
            s = added(inp, codes, target, RULE_ID, [s], placeholder, supporting)
            s = s.model_copy(update={"rule_results": []})
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
    return RuleOutput(suggestions=out, dropped=dropped, gaps=gaps)
