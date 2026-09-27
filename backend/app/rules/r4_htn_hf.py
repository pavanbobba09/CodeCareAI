"""R4: hypertension with heart failure -> I11.0 plus I50.x.

Source: ICD-10-CM Official Guidelines for Coding and Reporting FY2027, Section I.C.9.a.1
(Hypertension with Heart Disease: hypertension with heart failure (I50.-) is assigned to
I11; use an additional I50 code; code separately only if the provider documents the heart
failure as unrelated). Skipped when R5 (I13) applies.

When the note links the heart failure `caused_by` something other than the hypertension,
the link is not presumed and the codes are marked for review.
"""

from app.models import RuleInput, RuleOutput
from app.rules.common import Hypertension, added, present, result, review_all
from app.terminology.lookup import CodeLookup

RULE_ID = "R4"
SOURCE_REF = "ICD-10-CM Guidelines FY2027 §I.C.9.a.1"
TARGET_CODES = frozenset({"I11.0"})


def apply(inp: RuleInput, codes: CodeLookup) -> RuleOutput:
    h = Hypertension(inp)
    out = list(inp.suggestions)
    if not (h.htn and h.hf) or h.has_i13:
        return RuleOutput(suggestions=out, dropped=[], gaps=[])
    if not h.hf_linked:
        r = result(
            RULE_ID,
            "needs_review",
            "The note links the heart failure to another cause, so the hypertension link "
            "is not presumed; check whether I11.0 applies.",
            SOURCE_REF,
            [s.code for s in h.htn + h.hf],
        )
        return RuleOutput(suggestions=review_all(out, h.htn + h.hf, r), dropped=[], gaps=[])
    if any(s.code == "I11.0" for s in h.htn):
        return RuleOutput(suggestions=out, dropped=[], gaps=[])
    r = result(
        RULE_ID,
        "pass",
        "Hypertension with heart failure: I11.0 with the I50 code.",
        SOURCE_REF,
        ["I11.0", *(s.code for s in h.hf)],
    )
    if not present(out, "I11.0"):
        out.append(added(inp, codes, "I11.0", RULE_ID, h.htn + h.hf, r))
    return RuleOutput(suggestions=out, dropped=[], gaps=[])
