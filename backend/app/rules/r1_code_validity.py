"""R1: reject codes absent, inactive, non-billable, or invalid for the visit date.

Sources: ICD-10-CM Official Guidelines for Coding and Reporting FY2027, Section I.B.2
(Level of Detail in Coding: report codes to the highest number of characters available);
HIPAA code set standard, 45 CFR 162.1002 (use the code set in effect on the date of service).
"""

from app.models import DroppedCode, RuleInput, RuleOutput, RuleResult, Suggestion
from app.terminology.lookup import CodeLookup

RULE_ID = "R1"
SOURCE_REF = "ICD-10-CM Guidelines FY2027 §I.B.2; 45 CFR 162.1002"


def _problem(s: Suggestion, inp: RuleInput, codes: CodeLookup) -> str | None:
    code_set_id = inp.code_sets.cpt if s.system == "CPT" else inp.code_sets.icd10cm
    if code_set_id is None:
        return f"No {s.system} code set covers visit date {inp.visit_date.isoformat()}."
    if codes.get_code(s.code, code_set_id) is None:
        return f"{s.code} is not in {code_set_id}, the code set for the visit date."
    if not codes.is_billable(s.code, code_set_id):
        return f"{s.code} is not billable; a more specific code is required."
    return None


def apply(inp: RuleInput, codes: CodeLookup) -> RuleOutput:
    kept: list[Suggestion] = []
    dropped: list[DroppedCode] = []
    for s in inp.suggestions:
        problem = _problem(s, inp, codes)
        if problem is not None:
            dropped.append(
                DroppedCode(code=s.code, fact_ids=s.fact_ids, rule_id=RULE_ID, reason=problem)
            )
            continue
        result = RuleResult(
            rule_id=RULE_ID,
            outcome="pass",
            message=f"{s.code} is a valid billable code for the visit date.",
            source_ref=SOURCE_REF,
            affects_codes=[s.code],
        )
        kept.append(s.model_copy(update={"rule_results": [*s.rule_results, result]}))
    return RuleOutput(suggestions=kept, dropped=dropped, gaps=[])
