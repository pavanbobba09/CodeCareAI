"""R9: CKD stage or stage 3 subtype missing -> keep the less specific code, raise a gap.

Source: ICD-10-CM Official Guidelines for Coding and Reporting FY2027, Section I.C.14.a.1
(Stages of CKD: severity is stages 1-5; stage 3 is N18.30-N18.32; if both a stage and ESRD
are documented, assign N18.6 only).

Every selected N18 code is reconciled with the stage the CKD facts document, in both
directions: a more or a less specific selection is replaced by the documented stage's code
(N18.9 when CKD is documented without a stage), and when ESRD is documented every CKD code
becomes N18.6. The code's own CKD facts are used first, then all CKD facts. A selected N18
code with no documented CKD is kept as not suggested. The gap is raised only when the note
documents no stage (N18.9) or no 3a/3b (N18.30).
"""

from app.models import DroppedCode, Gap, RuleInput, RuleOutput, Suggestion
from app.rules.common import (
    N18_CODES,
    active,
    added,
    ckd_facts,
    documented_ckd_codes,
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
    ckd_f = ckd_facts(inp)
    esrd = documented_ckd_codes(ckd_f) == ["N18.6"]
    by_id = facts_by_id(inp)
    out: list[Suggestion] = []
    dropped: list[DroppedCode] = []
    gaps: list[Gap] = []
    for s in inp.suggestions:
        if s.suggestion_id not in live or not is_ckd(s.code):
            out.append(s)
            continue
        if not ckd_f:
            r = result(RULE_ID, "fail", f"{s.code} needs documented CKD.", SOURCE_REF, [s.code])
            out.append(with_result(s, r))
            continue
        own = [by_id[f] for f in s.fact_ids if f in by_id and by_id[f] in ckd_f] or ckd_f
        documented = ["N18.6"] if esrd else documented_ckd_codes(own)
        target = documented[0] if len(documented) == 1 else s.code  # conflict: leave it
        if target != s.code:
            dropped.append(
                DroppedCode(
                    code=s.code,
                    fact_ids=s.fact_ids,
                    rule_id=RULE_ID,
                    reason=f"The note documents {target}, not {s.code}.",
                )
            )
            if present(active(inp.suggestions), target) or present(out, target):
                continue
            # The replacement gets its R9 result below like any other CKD code.
            placeholder = result(RULE_ID, "pass", "", SOURCE_REF, [target])
            ids = sorted({*s.fact_ids, *(f.fact_id for f in own)})
            s = added(inp, codes, target, RULE_ID, [s], placeholder, ids)
            s = s.model_copy(update={"rule_results": []})
        elif present(out, s.code):
            continue  # an earlier suggestion was already reconciled to this code
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
                RULE_ID, "pass", f"{s.code} matches the documented stage.", SOURCE_REF, [s.code]
            )
            out.append(with_result(s, r))
    return RuleOutput(suggestions=out, dropped=dropped, gaps=gaps)
