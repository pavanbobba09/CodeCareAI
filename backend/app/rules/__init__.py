"""Deterministic coding rules R1-R14 (DESIGN.md §3.4), one module per rule.

Every rule is pure: apply(inp: RuleInput, codes: CodeLookup) -> RuleOutput.
No LLM calls and no db calls inside a rule.
"""

from collections.abc import Callable

from app.models import DroppedCode, Gap, RuleInput, RuleOutput
from app.rules import r1_code_validity
from app.terminology.lookup import CodeLookup

Rule = Callable[[RuleInput, CodeLookup], RuleOutput]

# Order matters: each rule sees the previous rule's kept suggestions.
ICD_RULES: list[Rule] = [r1_code_validity.apply]
# Skipped when CodeSetSelection.cpt is None (DESIGN.md §3.4). R13 and R14 arrive in M6.
CPT_RULES: list[Rule] = []


def run_all(inp: RuleInput, codes: CodeLookup) -> RuleOutput:
    rules = ICD_RULES + (CPT_RULES if inp.code_sets.cpt is not None else [])
    suggestions = inp.suggestions
    dropped: list[DroppedCode] = []
    gaps: list[Gap] = []
    for rule in rules:
        out = rule(inp.model_copy(update={"suggestions": suggestions}), codes)
        suggestions = out.suggestions
        dropped += out.dropped
        gaps += out.gaps
    return RuleOutput(suggestions=suggestions, dropped=dropped, gaps=gaps)
