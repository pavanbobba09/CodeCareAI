"""Rule contracts (DESIGN.md §5.2). Rules are pure: apply(inp, codes) -> RuleOutput."""

from datetime import date

from pydantic import BaseModel

from app.models.core import ClinicalFact, CodeSetSelection, Gap, Suggestion


class RuleInput(BaseModel):
    visit_date: date
    code_sets: CodeSetSelection
    facts: list[ClinicalFact]
    suggestions: list[Suggestion]


class DroppedCode(BaseModel):
    """A suggestion a rule removed outright, e.g. R1 for a code not valid on the visit date."""

    code: str
    fact_ids: list[str]
    rule_id: str
    reason: str


class RuleOutput(BaseModel):
    suggestions: list[Suggestion]  # kept suggestions, with this rule's RuleResult appended
    dropped: list[DroppedCode]
    gaps: list[Gap]
