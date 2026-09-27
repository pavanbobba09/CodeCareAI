"""R12: Excludes1 conflicts between suggested codes -> review both and raise a gap.

Source: ICD-10-CM Official Guidelines for Coding and Reporting FY2027, Section I.A.12.a
(Excludes1: the two codes are never used together, except when the two conditions are
unrelated to each other; if it is not clear whether they are related, query the provider).
Excludes1 notes on a category apply to every code under it. The rule never drops a code:
whether the exception applies is the coder's call.
"""

from itertools import combinations

from app.models import Gap, RuleInput, RuleOutput, Suggestion
from app.rules.common import active, result, with_result
from app.terminology.lookup import CodeLookup
from app.terminology.tabular import matches

RULE_ID = "R12"
SOURCE_REF = "ICD-10-CM Guidelines FY2027 §I.A.12.a"
TARGET_CODES: frozenset[str] = frozenset()


def _excludes(a: Suggestion, b: Suggestion, inp: RuleInput, codes: CodeLookup) -> bool:
    return any(matches(p, b.code) for p in codes.excludes1_of(a.code, inp.code_sets.icd10cm))


def apply(inp: RuleInput, codes: CodeLookup) -> RuleOutput:
    icd = [s for s in active(inp.suggestions) if s.system == "ICD-10-CM"]
    by_id = {s.suggestion_id: s for s in inp.suggestions}
    gaps: list[Gap] = []
    for a, b in combinations(icd, 2):
        if not (_excludes(a, b, inp, codes) or _excludes(b, a, inp, codes)):
            continue
        pair = sorted([a.code, b.code])
        gap = Gap(
            gap_id=f"{RULE_ID}-{pair[0]}-{pair[1]}",
            kind="conflicting",
            missing="whether the two conditions are related",
            affects_codes=pair,
            rule_id=RULE_ID,
            query_text=(
                f"The note supports both {a.description or a.code} and "
                f"{b.description or b.code}, which are normally not reported together. "
                "Please clarify whether these conditions are related."
            ),
            severity="review",
        )
        gaps.append(gap)
        r = result(
            RULE_ID,
            "needs_review",
            f"{pair[0]} and {pair[1]} have an Excludes1 note; report both only if the "
            "conditions are unrelated.",
            SOURCE_REF,
            pair,
        )
        for s in (a, b):
            by_id[s.suggestion_id] = with_result(by_id[s.suggestion_id], r, gap)
    return RuleOutput(
        suggestions=[by_id[s.suggestion_id] for s in inp.suggestions], dropped=[], gaps=gaps
    )
