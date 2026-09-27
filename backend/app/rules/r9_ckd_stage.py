"""R9: CKD stage or stage 3 subtype missing -> keep the less specific code, raise a gap.

Source: ICD-10-CM Official Guidelines for Coding and Reporting FY2027, Section I.C.14.a.1
(Stages of CKD: severity is stages 1-5; stage 3 is N18.30-N18.32; if both a stage and ESRD
are documented, assign N18.6 only).

The gap is raised only when the note documents no stage (or no 3a/3b for stage 3). When the
LLM picked N18.9 or N18.30 but the CKD fact states a more specific stage, the documented
stage code replaces it.
"""

from app.models import DroppedCode, Gap, RuleInput, RuleOutput, Suggestion
from app.rules.common import (
    N18_CODES,
    active,
    added,
    documented_stage_code,
    facts_by_id,
    is_ckd,
    present,
    result,
    with_result,
)
from app.terminology.lookup import CodeLookup

RULE_ID = "R9"
SOURCE_REF = "ICD-10-CM Guidelines FY2027 §I.C.14.a.1"
TARGET_CODES = N18_CODES
# Codes a documented stage may replace: any stage beats N18.9; only 3a/3b beat N18.30.
MORE_SPECIFIC = {"N18.9": N18_CODES - {"N18.9"}, "N18.30": {"N18.31", "N18.32"}}

# Neutral wording: ask for the missing fact, never for a code or a preferred answer.
MISSING = {
    "N18.9": (
        "CKD stage",
        "The note documents chronic kidney disease without a stage. "
        "Please document the stage, if known.",
    ),
    "N18.30": (
        "CKD stage 3 subtype (3a or 3b)",
        "The note documents chronic kidney disease stage 3 without 3a or 3b. "
        "Please document the subtype, if known.",
    ),
}


def apply(inp: RuleInput, codes: CodeLookup) -> RuleOutput:
    live = {s.suggestion_id for s in active(inp.suggestions)}
    ckd = [s for s in inp.suggestions if s.suggestion_id in live and is_ckd(s.code)]
    esrd = any(s.code == "N18.6" for s in ckd)
    out: list[Suggestion] = []
    dropped: list[DroppedCode] = []
    gaps: list[Gap] = []
    for s in inp.suggestions:
        if s.suggestion_id not in live or not is_ckd(s.code):
            out.append(s)
            continue
        if esrd and s.code != "N18.6":
            dropped.append(
                DroppedCode(
                    code=s.code,
                    fact_ids=s.fact_ids,
                    rule_id=RULE_ID,
                    reason="ESRD is documented; N18.6 only.",
                )
            )
            continue
        better = _documented(inp, s)
        if better is not None:
            dropped.append(
                DroppedCode(
                    code=s.code,
                    fact_ids=s.fact_ids,
                    rule_id=RULE_ID,
                    reason=f"The note documents the stage; {better} replaces {s.code}.",
                )
            )
            if present(inp.suggestions, better) or present(out, better):
                continue
            # The replacement gets its R9 result below like any other CKD code.
            placeholder = result(RULE_ID, "pass", "", SOURCE_REF, [better])
            s = added(inp, codes, better, RULE_ID, [s], placeholder, s.fact_ids)
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
            r = result(RULE_ID, "pass", f"{s.code} states the CKD stage.", SOURCE_REF, [s.code])
            out.append(with_result(s, r))
    return RuleOutput(suggestions=out, dropped=dropped, gaps=gaps)


def _documented(inp: RuleInput, s: Suggestion) -> str | None:
    """A more specific N18 code that the suggestion's own facts document, if any."""
    allowed = MORE_SPECIFIC.get(s.code, set())
    facts = facts_by_id(inp)
    found = {documented_stage_code(facts[f]) for f in s.fact_ids if f in facts}
    better = sorted(c for c in found if c is not None and c in allowed)
    return better[0] if len(better) == 1 else None
