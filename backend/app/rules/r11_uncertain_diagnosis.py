"""R11: outpatient probable/suspected/rule-out diagnoses are not coded as confirmed.

Source: ICD-10-CM Official Guidelines for Coding and Reporting FY2027, Section IV.H
(Uncertain diagnosis: do not code diagnoses documented as "probable", "suspected",
"rule out" or similar; code signs, symptoms or other reasons for the visit instead).

Facts with these statuses get no candidates, so this rule is a guard: a suggestion whose
facts are all uncertain, ruled out or denied is kept only as "not suggested", so the coder
sees why. Later rules ignore it.
"""

from app.models import RuleInput, RuleOutput
from app.rules.common import (
    code_condition_families,
    condition_families,
    facts_by_id,
    result,
    with_result,
)
from app.terminology.lookup import CodeLookup

RULE_ID = "R11"
SOURCE_REF = "ICD-10-CM Guidelines FY2027 §IV.H"
TARGET_CODES: frozenset[str] = frozenset()
NOT_CODED = {"suspected", "ruled_out", "denied"}


def apply(inp: RuleInput, codes: CodeLookup) -> RuleOutput:
    facts = facts_by_id(inp)
    kept = []
    for s in inp.suggestions:
        families = code_condition_families(s.code)
        related = [
            facts[f]
            for f in s.fact_ids
            if f in facts and condition_families(facts[f]) & families
        ]
        statuses = {f.status for f in related}
        if statuses and statuses <= NOT_CODED:
            r = result(
                RULE_ID,
                "fail",
                f"{s.code} rests only on {', '.join(sorted(statuses))} documentation; "
                "outpatient uncertain diagnoses are not coded.",
                SOURCE_REF,
                [s.code],
            )
            s = with_result(s, r)
        kept.append(s)
    return RuleOutput(suggestions=kept, dropped=[], gaps=[])
