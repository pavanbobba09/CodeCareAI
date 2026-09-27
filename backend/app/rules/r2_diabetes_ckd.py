"""R2: diabetes with CKD -> E1x.22 plus the documented N18 stage code.

Sources: ICD-10-CM Official Guidelines for Coding and Reporting FY2027, Section I.A.15
("With": the classification presumes a causal relationship between conditions linked by
"with" in the Index, unless the documentation clearly states they are unrelated); Tabular
E11.22 "Use additional code to identify stage of chronic kidney disease (N18.1-N18.6)".

Diabetes and CKD count only when active facts document them; a selected E1x.22 is never
its own evidence. A selected E1x.22 without both documented is kept as not suggested.
E1x.22 replaces only the uncomplicated E1x.9; other complications (E1x.21, E1x.29, E1x.65)
stay and E1x.22 is added next to them. When the note links the CKD `caused_by` something
other than the diabetes, the link is not presumed and the codes are marked for review.
The N18 code comes from the stage the CKD facts document (N18.9 when none is written).
Secondary diabetes (E08, E09, E13) is out of scope (DESIGN.md known limits).
"""

from app.models import DroppedCode, RuleInput, RuleOutput, Suggestion
from app.rules.common import (
    N18_CODES,
    Conditions,
    active,
    added,
    caused_by_other,
    fail_all,
    ids_of,
    is_ckd,
    is_diabetes,
    owns_families,
    present,
    result,
    review_all,
    stage_additions,
)
from app.terminology.lookup import CodeLookup

RULE_ID = "R2"
SOURCE_REF = "ICD-10-CM Guidelines FY2027 §I.A.15; Tabular E11.22 use additional code"
TARGET_CODES = frozenset({"E10.22", "E11.22", *N18_CODES})


def apply(inp: RuleInput, codes: CodeLookup) -> RuleOutput:
    out: list[Suggestion] = list(inp.suggestions)
    dropped: list[DroppedCode] = []
    c = Conditions(inp)
    combinations = [
        s
        for s in active(out)
        if is_diabetes(s.code) and s.code.endswith(".22")
    ]
    unowned = [s for s in combinations if not owns_families(inp, s, "diabetes", "ckd")]
    if unowned:
        r = result(
            RULE_ID,
            "fail",
            "A diabetes-with-CKD code needs its own active diabetes and CKD facts.",
            SOURCE_REF,
            [s.code for s in unowned],
        )
        out = fail_all(out, unowned, r)
    for prefix in ("E10", "E11"):
        target = f"{prefix}.22"
        dm = [s for s in active(out) if s.code.startswith(prefix)]
        if not dm:
            continue
        combo = [s for s in dm if s.code == target]
        if not (c.diabetes and c.ckd):
            if combo:
                missing = (
                    "diabetes and CKD"
                    if not c.diabetes and not c.ckd
                    else ("diabetes" if not c.diabetes else "CKD")
                )
                r = result(
                    RULE_ID,
                    "fail",
                    f"{target} needs documented diabetes and CKD; the note does not document "
                    f"{missing}.",
                    SOURCE_REF,
                    [target],
                )
                out = fail_all(out, combo, r)
            continue
        if caused_by_other(inp, ids_of(c.ckd), ids_of(c.diabetes)):
            r = result(
                RULE_ID,
                "needs_review",
                "The note links the CKD to another cause, so the diabetes-CKD link is not "
                f"presumed; check whether {target} applies.",
                SOURCE_REF,
                [s.code for s in dm],
            )
            ckd_codes = [s for s in active(out) if is_ckd(s.code)]
            out = review_all(out, dm + ckd_codes, r)
            continue
        r = result(
            RULE_ID,
            "pass",
            f"Diabetes and CKD are both documented; {target} with the N18 stage code "
            '(link presumed by "with").',
            SOURCE_REF,
            [target],
        )
        for s in dm:
            if s.code == f"{prefix}.9":  # only "without complications" is replaced
                dropped.append(
                    DroppedCode(
                        code=s.code,
                        fact_ids=s.fact_ids,
                        rule_id=RULE_ID,
                        reason=f"Replaced by {target}: diabetes with CKD is not uncomplicated.",
                    )
                )
                out = [x for x in out if x.suggestion_id != s.suggestion_id]
        if not present(active(out), target):
            ids = ids_of([*c.diabetes, *c.ckd])
            out.append(added(inp, codes, target, RULE_ID, dm, r, ids))
        out += stage_additions(
            inp.model_copy(update={"suggestions": out}), codes, RULE_ID, r, c.ckd
        )
    return RuleOutput(suggestions=out, dropped=dropped, gaps=[])
