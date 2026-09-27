"""Small builders for rule tests: facts, suggestions, and an in-memory FY2027 code table."""

from datetime import date

from app.models import ClinicalFact, CodeSetSelection, RuleInput, RuleOutput, Suggestion
from app.rules import Rule, run_all
from app.terminology.lookup import CodeRecord, InMemoryCodeLookup

CS = "ICD10CM-FY2027"
SETS = CodeSetSelection(icd10cm=CS, cpt=None)

# (code, billable, parent, own Excludes1 patterns); descriptions are shortened.
_TABLE = [
    ("E10", False, None, ("E08", "E09", "E11", "E13")),
    ("E10.2", False, "E10", ()),
    ("E10.22", True, "E10.2", ()),
    ("E10.9", True, "E10", ()),
    ("E11", False, None, ("E08", "E09", "E10", "E13")),
    ("E11.2", False, "E11", ()),
    ("E11.21", True, "E11.2", ()),
    ("E11.22", True, "E11.2", ()),
    ("E11.6", False, "E11", ()),
    ("E11.65", True, "E11.6", ()),
    ("E11.9", True, "E11", ()),
    ("E13", False, None, ("E08", "E09", "E10", "E11")),
    ("E13.9", True, "E13", ()),
    ("I10", True, None, ("O10-O11", "O13-O16")),
    ("I11", False, None, ()),
    ("I11.0", True, "I11", ()),
    ("I11.9", True, "I11", ()),
    ("I12", False, None, ("I15",)),
    ("I12.0", True, "I12", ()),
    ("I12.9", True, "I12", ()),
    ("I13", False, None, ()),
    ("I13.0", True, "I13", ()),
    ("I13.1", False, "I13", ()),
    ("I13.10", True, "I13.1", ()),
    ("I13.11", True, "I13.1", ()),
    ("I13.2", True, "I13", ()),
    ("I50", False, None, ()),
    ("I50.1", True, "I50", ()),
    ("I50.2", False, "I50", ("I50.4",)),
    ("I50.20", True, "I50.2", ()),
    ("I50.21", True, "I50.2", ()),
    ("I50.22", True, "I50.2", ()),
    ("I50.23", True, "I50.2", ()),
    ("I50.3", False, "I50", ()),
    ("I50.30", True, "I50.3", ()),
    ("I50.31", True, "I50.3", ()),
    ("I50.32", True, "I50.3", ()),
    ("I50.33", True, "I50.3", ()),
    ("I50.4", False, "I50", ()),
    ("I50.40", True, "I50.4", ()),
    ("I50.41", True, "I50.4", ()),
    ("I50.42", True, "I50.4", ()),
    ("I50.43", True, "I50.4", ()),
    ("I50.9", True, "I50", ()),
    ("N18", False, None, ()),
    ("N18.3", False, "N18", ()),
    ("N18.30", True, "N18.3", ()),
    ("N18.31", True, "N18.3", ()),
    ("N18.32", True, "N18.3", ()),
    ("N18.4", True, "N18", ()),
    ("N18.5", True, "N18", ()),
    ("N18.6", True, "N18", ()),
    ("N18.9", True, "N18", ()),
    ("R06.02", True, None, ()),
    ("Z79.4", True, None, ()),
    ("Z79.84", True, None, ()),
    ("Z79.85", True, None, ()),
]


def lookup(
    without: set[str] | None = None,
    not_billable: set[str] | None = None,
    extra: dict[tuple[str, str], CodeRecord] | None = None,
) -> InMemoryCodeLookup:
    """The FY2027 test table, minus `without`, with `not_billable` flipped, plus `extra`."""
    records = {
        (CS, code): CodeRecord(
            code=code,
            system="ICD-10-CM",
            description=f"desc {code}",
            billable=billable and code not in (not_billable or set()),
            parent_code=parent,
            excludes1=excl,
        )
        for code, billable, parent, excl in _TABLE
        if code not in (without or set())
    }
    return InMemoryCodeLookup({**records, **(extra or {})})


LOOKUP = lookup()


def fact(
    fid: str,
    concept: str,
    evidence: list[int],
    *,
    kind: str = "condition",
    status: str = "active",
    details: dict[str, str] | None = None,
    caused_by: str | None = None,
) -> ClinicalFact:
    return ClinicalFact.model_validate(
        {
            "fact_id": fid,
            "kind": kind,
            "concept": concept,
            "status": status,
            "details": details or {},
            "links": [{"type": "caused_by", "target_fact_id": caused_by}] if caused_by else [],
            "evidence": evidence,
        }
    )


def sug(sid: str, code: str, fact_ids: list[str], evidence: list[int] | None = None) -> Suggestion:
    return Suggestion(
        suggestion_id=sid,
        code=code,
        system="ICD-10-CM",
        description=f"desc {code}",
        fact_ids=fact_ids,
        evidence=evidence or [1],
        rule_results=[],
        gap_ids=[],
        confidence="review",
    )


def inp(suggestions: list[Suggestion], facts: list[ClinicalFact]) -> RuleInput:
    return RuleInput(
        visit_date=date(2026, 10, 15), code_sets=SETS, facts=facts, suggestions=suggestions
    )


def run(
    rule: Rule,
    suggestions: list[Suggestion],
    facts: list[ClinicalFact],
    codes: InMemoryCodeLookup = LOOKUP,
) -> RuleOutput:
    return rule(inp(suggestions, facts), codes)


def run_chain(
    suggestions: list[Suggestion],
    facts: list[ClinicalFact],
    codes: InMemoryCodeLookup = LOOKUP,
) -> RuleOutput:
    return run_all(inp(suggestions, facts), codes)


def codes_of(out: RuleOutput) -> list[str]:
    return sorted(s.code for s in out.suggestions)


def by_code(out: RuleOutput, code: str) -> Suggestion:
    return next(s for s in out.suggestions if s.code == code)


def outcomes(s: Suggestion, rule_id: str) -> list[str]:
    return [r.outcome for r in s.rule_results if r.rule_id == rule_id]
