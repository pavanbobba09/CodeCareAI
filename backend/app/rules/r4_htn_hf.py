"""R4: hypertension with heart failure -> I11.0 plus I50.x.

Source: ICD-10-CM Official Guidelines for Coding and Reporting FY2027, Section I.C.9.a.1
(Hypertension with Heart Disease: hypertension with heart failure (I50.-) is assigned to
I11; use an additional I50 code; code separately only if the provider documents the heart
failure as unrelated). Skipped when R5 (I13) applies.

Both conditions must be documented by active facts. With heart failure documented, I11.9
(without heart failure) becomes I11.0; a selected I11.0 without documented heart failure,
or any I11 without documented hypertension, is kept as not suggested. When the note links
the heart failure `caused_by` something other than the hypertension, the link is not
presumed and the codes are marked for review.
"""

from app.models import DroppedCode, RuleInput, RuleOutput
from app.rules.common import (
    HF_CODES,
    Conditions,
    active,
    adopt_documented_parts,
    fail_all,
    heart_failure_additions,
    ids_of,
    is_heart_failure,
    is_hypertension,
    owns_families,
    result,
    review_all,
    settle_variant,
)
from app.terminology.lookup import CodeLookup

RULE_ID = "R4"
SOURCE_REF = "ICD-10-CM Guidelines FY2027 §I.C.9.a.1"
TARGET_CODES = frozenset({"I11.0", *HF_CODES})
VARIANTS = {"I11.0", "I11.9"}


def apply(inp: RuleInput, codes: CodeLookup) -> RuleOutput:
    out = list(inp.suggestions)
    dropped: list[DroppedCode] = []
    htn_codes = [s for s in active(out) if is_hypertension(s.code)]
    if not htn_codes or any(s.code.startswith("I13") for s in htn_codes):
        return RuleOutput(suggestions=out, dropped=dropped, gaps=[])
    c = Conditions(inp)
    out = adopt_documented_parts(
        inp, out, [s for s in htn_codes if s.code.startswith("I11")], "hypertension"
    )
    htn_codes = [s for s in active(out) if is_hypertension(s.code)]
    i11 = [s for s in htn_codes if s.code.startswith("I11")]
    unowned = [
        s
        for s in i11
        if not owns_families(
            inp, s, "hypertension", *(("heart_failure",) if s.code == "I11.0" else ())
        )
    ]
    unsupported = list(
        {
            s.suggestion_id: s
            for s in [
                *unowned,
                *(i11 if not c.htn else [s for s in i11 if s.code == "I11.0" and not c.hf]),
            ]
        }.values()
    )
    if unsupported:
        r = result(
            RULE_ID,
            "fail",
            "An I11 code needs its own active hypertension fact; I11.0 also needs its own "
            "active heart-failure fact.",
            SOURCE_REF,
            [s.code for s in unsupported],
        )
        out = fail_all(out, unsupported, r)
    if not (c.htn and c.hf):
        return RuleOutput(suggestions=out, dropped=dropped, gaps=[])
    if not c.hf_linked:
        r = result(
            RULE_ID,
            "needs_review",
            "The note links the heart failure to another cause, so the hypertension link "
            "is not presumed; check whether I11.0 applies.",
            SOURCE_REF,
            [s.code for s in htn_codes],
        )
        hf_codes = [s for s in active(out) if is_heart_failure(s.code)]
        return RuleOutput(
            suggestions=review_all(out, htn_codes + hf_codes, r), dropped=dropped, gaps=[]
        )
    r = result(
        RULE_ID,
        "pass",
        "Hypertension with heart failure: I11.0 with the I50 code.",
        SOURCE_REF,
        ["I11.0"],
    )
    ids = ids_of([*c.htn, *c.hf])
    out, dropped = settle_variant(inp, codes, out, VARIANTS, "I11.0", RULE_ID, r, ids)
    out += heart_failure_additions(
        inp.model_copy(update={"suggestions": out}), codes, RULE_ID, r, c.hf
    )
    return RuleOutput(suggestions=out, dropped=dropped, gaps=[])
