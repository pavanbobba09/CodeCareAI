"""Confidence bands and same-condition conflicts (DESIGN.md §5.1). Pure functions.

Bands: "not_suggested" when R11 failed the code (uncertain diagnosis); "review" when any
rule result needs review or a gap is linked; "strong" when every rule result passed, the
code has evidence, and no gap is linked.
"""

from app.models import Confidence, Gap, Suggestion

# Families where two different codes for one note mean the documentation conflicts,
# e.g. two CKD stages (N18.31 and N18.4) or two heart failure types (I50.20 and I50.9).
FAMILIES = {"N18": "CKD stage", "I50": "heart failure type or acuity"}


def band(s: Suggestion) -> Confidence:
    outcomes = {r.outcome for r in s.rule_results}
    if "fail" in outcomes:
        return "not_suggested"
    if "needs_review" in outcomes or s.gap_ids or not s.evidence:
        return "review"
    return "strong"


def conflicts(suggestions: list[Suggestion]) -> tuple[list[Suggestion], list[Gap]]:
    """Link a "conflicting" gap to every code in a family that has more than one code."""
    gaps: list[Gap] = []
    out = list(suggestions)
    for prefix, what in FAMILIES.items():
        members = [s for s in out if s.code.startswith(prefix) and band(s) != "not_suggested"]
        codes = sorted({s.code for s in members})
        if len(codes) < 2:
            continue
        gap = Gap(
            gap_id=f"conflict-{prefix}",
            kind="conflicting",
            missing=what,
            affects_codes=codes,
            rule_id=None,
            query_text=(
                f"The note supports more than one {what} ({', '.join(codes)}). "
                "Please clarify which one applies."
            ),
            severity="review",
        )
        gaps.append(gap)
        ids = {s.suggestion_id for s in members}
        out = [
            s.model_copy(update={"gap_ids": [*s.gap_ids, gap.gap_id]})
            if s.suggestion_id in ids
            else s
            for s in out
        ]
    return out, gaps


def finalize(suggestions: list[Suggestion], gaps: list[Gap]) -> tuple[list[Suggestion], list[Gap]]:
    suggestions, conflict_gaps = conflicts(suggestions)
    return [s.model_copy(update={"confidence": band(s)}) for s in suggestions], [
        *gaps,
        *conflict_gaps,
    ]
