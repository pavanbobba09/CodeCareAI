"""Helpers shared by the ICD-10-CM rules. Pure: no LLM, no db."""

import re
from collections.abc import Iterable

from app.models import ClinicalFact, Gap, RuleInput, RuleResult, Suggestion
from app.terminology.lookup import CodeLookup


def is_diabetes(code: str) -> bool:
    return code[:3] in {"E08", "E09", "E10", "E11", "E13"}


def is_ckd(code: str) -> bool:
    return code.startswith("N18.")


def is_heart_failure(code: str) -> bool:
    return code.startswith("I50")


def is_hypertension(code: str) -> bool:
    """Essential hypertension or a hypertensive combination (I10, I11.-, I12.-, I13.-)."""
    return code == "I10" or code[:3] in {"I11", "I12", "I13"}


def not_suggested(s: Suggestion) -> bool:
    """R11 kept this suggestion only to explain why it is not coded."""
    return any(r.rule_id == "R11" and r.outcome == "fail" for r in s.rule_results)


def active(suggestions: Iterable[Suggestion]) -> list[Suggestion]:
    return [s for s in suggestions if not not_suggested(s)]


def fact_ids(suggestions: Iterable[Suggestion]) -> list[str]:
    return sorted({f for s in suggestions for f in s.fact_ids})


def facts_by_id(inp: RuleInput) -> dict[str, ClinicalFact]:
    return {f.fact_id: f for f in inp.facts}


def caused_by_other(inp: RuleInput, condition_ids: Iterable[str], cause_ids: Iterable[str]) -> bool:
    """True when a `condition` fact is linked `caused_by` a fact outside `cause_ids`.

    The guidelines presume the diabetes-CKD and hypertension-CKD/heart failure links
    (I.A.15, I.C.9.a) unless the note ties the condition to something else.
    """
    facts = facts_by_id(inp)
    causes = set(cause_ids)
    for fid in set(condition_ids):
        fact = facts.get(fid)
        if fact is None:
            continue
        for link in fact.links:
            if link.type == "caused_by" and link.target_fact_id not in causes:
                return True
    return False


def evidence_of(inp: RuleInput, ids: Iterable[str], fallback: Iterable[Suggestion]) -> list[int]:
    """Sentence numbers of the facts that trigger a rule (their suggestions' if no facts)."""
    facts = facts_by_id(inp)
    found = {n for fid in ids if fid in facts for n in facts[fid].evidence}
    return sorted(found or {n for s in fallback for n in s.evidence})


def result(
    rule_id: str, outcome: str, message: str, source_ref: str, codes: list[str]
) -> RuleResult:
    return RuleResult.model_validate(
        {
            "rule_id": rule_id,
            "outcome": outcome,
            "message": message,
            "source_ref": source_ref,
            "affects_codes": codes,
        }
    )


def with_result(s: Suggestion, r: RuleResult, gap: Gap | None = None) -> Suggestion:
    update: dict[str, object] = {"rule_results": [*s.rule_results, r]}
    if gap is not None:
        update["gap_ids"] = [*s.gap_ids, gap.gap_id]
    return s.model_copy(update=update)


def added(
    inp: RuleInput,
    codes: CodeLookup,
    code: str,
    rule_id: str,
    triggers: list[Suggestion],
    r: RuleResult,
    trigger_fact_ids: list[str] | None = None,
) -> Suggestion:
    """A suggestion a rule adds from the code table. R1 checks it at the end of the chain;
    its id is assigned by run_all."""
    found = codes.get_code(code, inp.code_sets.icd10cm)
    ids = trigger_fact_ids if trigger_fact_ids is not None else fact_ids(triggers)
    return Suggestion(
        suggestion_id="",
        code=code,
        system="ICD-10-CM",
        description=found.description if found else "",
        fact_ids=ids,
        evidence=evidence_of(inp, ids, triggers),
        rule_results=[r],
        gap_ids=[],
        confidence="review",
        added_by_rule=rule_id,
    )


def present(suggestions: Iterable[Suggestion], code: str) -> bool:
    return any(s.code == code for s in suggestions)


def stage5_or_esrd(ckd: Iterable[Suggestion]) -> bool:
    return any(s.code in {"N18.5", "N18.6"} for s in ckd)


class Hypertension:
    """What the hypertension rules (R3-R5) need to know about one note.

    CKD counts as present when an N18 code was selected, an I12/I13 code was selected
    (both include CKD), or an active fact documents CKD without an N18 code picked.
    """

    def __init__(self, inp: RuleInput) -> None:
        live = active(inp.suggestions)
        self.htn = [s for s in live if is_hypertension(s.code)]
        self.hf = [s for s in live if is_heart_failure(s.code)]
        self.ckd = [s for s in live if is_ckd(s.code)]
        self.ckd_facts = ckd_facts(inp)
        self.has_i13 = any(s.code.startswith("I13") for s in self.htn)
        self.has_ckd = bool(
            self.ckd or self.ckd_facts or any(s.code[:3] in {"I12", "I13"} for s in self.htn)
        )
        htn_ids = fact_ids(self.htn)
        self.ckd_ids = sorted({*fact_ids(self.ckd), *(f.fact_id for f in self.ckd_facts)})
        # I.C.9.a presumes the link unless the note ties the condition to another cause.
        self.hf_linked = bool(self.htn and self.hf) and not caused_by_other(
            inp, fact_ids(self.hf), htn_ids
        )
        self.ckd_linked = bool(self.htn and self.has_ckd) and not caused_by_other(
            inp, self.ckd_ids, htn_ids
        )

    def stage5_or_esrd(self) -> bool:
        if self.ckd:
            return stage5_or_esrd(self.ckd)
        return any(documented_stage_code(f) in {"N18.5", "N18.6"} for f in self.ckd_facts)


def review_all(
    suggestions: list[Suggestion], targets: Iterable[Suggestion], r: RuleResult
) -> list[Suggestion]:
    ids = {s.suggestion_id for s in targets}
    return [with_result(s, r) if s.suggestion_id in ids else s for s in suggestions]


# CKD stage -> N18 code (I.C.14.a.1: stages 1-5, stage 3 split 3a/3b; ESRD is N18.6).
STAGE_CODES = {
    "1": "N18.1",
    "2": "N18.2",
    "3": "N18.30",
    "3a": "N18.31",
    "3b": "N18.32",
    "4": "N18.4",
    "5": "N18.5",
}
N18_CODES = frozenset({*STAGE_CODES.values(), "N18.6", "N18.9"})
_CKD = re.compile(
    r"chronic kidney|\bckd\b|kidney disease|end[- ]stage (renal|kidney)|\besrd\b|\beskd\b",
    re.IGNORECASE,
)
_ESRD = re.compile(r"end[- ]stage (renal|kidney)|\besrd\b|\beskd\b", re.IGNORECASE)
_STAGE = re.compile(r"\bstage\s*(1|2|3a|3b|3|4|5)\b|^\s*(1|2|3a|3b|3|4|5)\s*$", re.IGNORECASE)


def ckd_facts(inp: RuleInput) -> list[ClinicalFact]:
    """Active condition facts about chronic kidney disease (including combined facts)."""
    return [
        f
        for f in inp.facts
        if f.kind == "condition" and f.status == "active" and _CKD.search(f.concept)
    ]


def documented_stage_code(fact: ClinicalFact) -> str | None:
    """The N18 code for the stage the fact documents, or None when no stage is written."""
    for text in (fact.details.get("stage", ""), fact.concept):
        if _ESRD.search(text):
            return "N18.6"
        m = _STAGE.search(text)
        if m:
            return STAGE_CODES[(m[1] or m[2]).lower()]
    return None


def stage_additions(
    inp: RuleInput, codes: CodeLookup, rule_id: str, r: RuleResult, facts: list[ClinicalFact]
) -> list[Suggestion]:
    """N18 codes to add when a CKD combination is coded but no N18 code was selected.

    The combination codes say "use additional code to identify the stage" (Tabular E11.22,
    I12, I13). A documented stage gives its code; no stage gives N18.9, which R9 flags.
    """
    if any(is_ckd(s.code) for s in active(inp.suggestions)) or not facts:
        return []
    by_code: dict[str, list[str]] = {}
    for f in facts:
        by_code.setdefault(documented_stage_code(f) or "N18.9", []).append(f.fact_id)
    staged = {c: ids for c, ids in by_code.items() if c != "N18.9"}
    return [
        added(inp, codes, code, rule_id, [], r, sorted(ids))
        for code, ids in sorted((staged or by_code).items())
    ]
