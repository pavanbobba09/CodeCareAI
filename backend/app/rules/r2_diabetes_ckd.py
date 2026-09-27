"""R2: diabetes with CKD -> E1x.22 plus the documented N18 stage code.

Sources: ICD-10-CM Official Guidelines for Coding and Reporting FY2027, Section I.A.15
("With": the classification presumes a causal relationship between conditions linked by
"with" in the Index, unless the documentation clearly states they are unrelated); Tabular
E11.22 "Use additional code to identify stage of chronic kidney disease (N18.1-N18.6)".

When the note links the CKD `caused_by` something other than the diabetes, the link is not
presumed and both codes are marked for review. When E1x.22 is coded but no N18 code was
selected, the stage the CKD fact documents is added (N18.9 when none is written, which R9
flags). Secondary diabetes (E08, E09, E13) is out of scope (DESIGN.md known limits).
"""

from app.models import DroppedCode, RuleInput, RuleOutput, Suggestion
from app.rules.common import (
    N18_CODES,
    active,
    added,
    caused_by_other,
    ckd_facts,
    fact_ids,
    is_ckd,
    present,
    result,
    review_all,
    stage_additions,
)
from app.terminology.lookup import CodeLookup

RULE_ID = "R2"
SOURCE_REF = "ICD-10-CM Guidelines FY2027 §I.A.15; Tabular E11.22 use additional code"
TARGET_CODES = frozenset({"E10.22", "E11.22", *N18_CODES})
KIDNEY = {".21", ".22", ".29"}  # diabetic nephropathy, CKD, other kidney complication


def apply(inp: RuleInput, codes: CodeLookup) -> RuleOutput:
    out: list[Suggestion] = list(inp.suggestions)
    dropped: list[DroppedCode] = []
    cfacts = ckd_facts(inp)
    for prefix in ("E10", "E11"):
        live = active(out)
        dm = [s for s in live if s.code.startswith(prefix)]
        ckd = [s for s in live if is_ckd(s.code)]
        if not dm or not (ckd or cfacts):
            continue
        target = f"{prefix}.22"
        ckd_ids = sorted({*fact_ids(ckd), *(f.fact_id for f in cfacts)})
        dm_ids = fact_ids(dm)
        if caused_by_other(inp, ckd_ids, dm_ids):
            r = result(
                RULE_ID,
                "needs_review",
                "The note links the CKD to another cause, so the diabetes-CKD link is not "
                f"presumed; check whether {target} applies.",
                SOURCE_REF,
                [s.code for s in dm + ckd],
            )
            out = review_all(out, dm + ckd, r)
            continue
        r = result(
            RULE_ID,
            "pass",
            f"Diabetes and CKD are both documented; {target} with the N18 stage code "
            '(link presumed by "with").',
            SOURCE_REF,
            [target],
        )
        other_kidney = any(s.code[3:] in KIDNEY and s.code != target for s in dm)
        if not other_kidney:
            for s in dm:
                if s.code == f"{prefix}.9":  # "without complications" is replaced
                    dropped.append(
                        DroppedCode(
                            code=s.code,
                            fact_ids=s.fact_ids,
                            rule_id=RULE_ID,
                            reason=f"Replaced by {target}: diabetes with CKD is not uncomplicated.",
                        )
                    )
                    out = [x for x in out if x.suggestion_id != s.suggestion_id]
            if not present(out, target):
                out.append(
                    added(inp, codes, target, RULE_ID, dm + ckd, r, sorted({*dm_ids, *ckd_ids}))
                )
        if present(out, target):
            staged = inp.model_copy(update={"suggestions": out})
            out += stage_additions(staged, codes, RULE_ID, r, cfacts)
    return RuleOutput(suggestions=out, dropped=dropped, gaps=[])
