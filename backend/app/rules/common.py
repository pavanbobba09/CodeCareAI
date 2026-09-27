"""Helpers shared by the ICD-10-CM rules. Pure: no LLM, no db."""

import re
from collections.abc import Iterable
from typing import Literal

from app.models import ClinicalFact, DroppedCode, Gap, RuleInput, RuleResult, Suggestion
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
    """A rule failed this code (R11 uncertain diagnosis, or a combination code whose parts
    are not documented). It is kept only to show the coder why it is not reported."""
    return any(r.outcome == "fail" for r in s.rule_results)


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


def review_all(
    suggestions: list[Suggestion], targets: Iterable[Suggestion], r: RuleResult
) -> list[Suggestion]:
    ids = {s.suggestion_id for s in targets}
    return [with_result(s, r) if s.suggestion_id in ids else s for s in suggestions]


# Conditions are documented only by active condition facts (a combined fact such as
# "hypertension with chronic kidney disease stage 5" documents both). A selected code is
# never evidence that its own parts are documented. These patterns include common
# Alphabetic Index terms, not just the preferred clinical names.
ConditionFamily = Literal["diabetes", "hypertension", "ckd", "heart_failure"]
DIABETES_TEXT = re.compile(r"diabet|\bdm\s*[12]?\b|\bt[12]dm\b|\bn?iddm\b", re.IGNORECASE)
CKD_TEXT = re.compile(
    r"chronic kidney|\bckd\b|kidney disease|chronic renal (?:disease|failure|insufficiency)"
    r"|end[- ]stage (renal|kidney)|\besrd\b|\beskd\b",
    re.IGNORECASE,
)
HEART_FAILURE_TEXT = re.compile(
    r"heart failure|cardiac failure|(?:left|right|bi)[ -]?ventricular failure|\bchf\b|\bhf\b"
    r"|\bhf(r|p|mr)ef\b",
    re.IGNORECASE,
)
HYPERTENSION_TEXT = re.compile(r"hypertensi|\bhtn\b|high blood pressure", re.IGNORECASE)
FAMILY_PATTERNS: dict[ConditionFamily, re.Pattern[str]] = {
    "diabetes": DIABETES_TEXT,
    "hypertension": HYPERTENSION_TEXT,
    "ckd": CKD_TEXT,
    "heart_failure": HEART_FAILURE_TEXT,
}


def condition_families(fact: ClinicalFact) -> frozenset[ConditionFamily]:
    """Condition families named by one condition fact, independent of status.

    A combined fact may name more than one family. Callers separately decide whether an
    active, suspected, historical or denied fact is appropriate for their check.
    """
    if fact.kind != "condition":
        return frozenset()
    return frozenset(
        family for family, pattern in FAMILY_PATTERNS.items() if pattern.search(fact.concept)
    )


def code_condition_families(code: str) -> frozenset[ConditionFamily]:
    """Condition families a code itself asserts, including combination-code parts."""
    families: set[ConditionFamily] = set()
    if is_diabetes(code):
        families.add("diabetes")
        if code.endswith(".22"):
            families.add("ckd")
    if is_hypertension(code):
        families.add("hypertension")
        if code.startswith("I11.0"):
            families.add("heart_failure")
        if code.startswith("I12") or code.startswith("I13"):
            families.add("ckd")
        if code.startswith("I13.0") or code.startswith("I13.2"):
            families.add("heart_failure")
    if is_ckd(code):
        families.add("ckd")
    if is_heart_failure(code):
        families.add("heart_failure")
    return frozenset(families)


def _documented(inp: RuleInput, family: ConditionFamily) -> list[ClinicalFact]:
    return [
        f
        for f in inp.facts
        if f.status == "active" and family in condition_families(f)
    ]


def diabetes_facts(inp: RuleInput) -> list[ClinicalFact]:
    return _documented(inp, "diabetes")


def ckd_facts(inp: RuleInput) -> list[ClinicalFact]:
    return _documented(inp, "ckd")


def heart_failure_facts(inp: RuleInput) -> list[ClinicalFact]:
    return _documented(inp, "heart_failure")


def hypertension_facts(inp: RuleInput) -> list[ClinicalFact]:
    return _documented(inp, "hypertension")


def own_family_facts(
    inp: RuleInput, suggestion: Suggestion, family: ConditionFamily
) -> list[ClinicalFact]:
    """Active facts in a suggestion's own fact_ids that document `family`."""
    by_id = facts_by_id(inp)
    return [
        by_id[fid]
        for fid in suggestion.fact_ids
        if fid in by_id
        and by_id[fid].status == "active"
        and family in condition_families(by_id[fid])
    ]


def owns_families(inp: RuleInput, suggestion: Suggestion, *families: ConditionFamily) -> bool:
    return all(own_family_facts(inp, suggestion, family) for family in families)


def ids_of(facts: Iterable[ClinicalFact]) -> list[str]:
    return sorted({f.fact_id for f in facts})


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
ESRD_TEXT = re.compile(r"end[- ]stage (renal|kidney)|\besrd\b|\beskd\b", re.IGNORECASE)
_STAGE = re.compile(r"\bstage\s*(1|2|3a|3b|3|4|5)\b|^\s*(1|2|3a|3b|3|4|5)\s*$", re.IGNORECASE)


def documented_stage_code(fact: ClinicalFact) -> str | None:
    """The N18 code for the stage the fact documents (details first, then the concept), or
    None when no stage is written. ESRD wins over a stage (I.C.14.a.1: N18.6 only)."""
    texts = (fact.details.get("stage", ""), fact.concept)
    if any(ESRD_TEXT.search(t) for t in texts):
        return "N18.6"
    for text in texts:
        m = _STAGE.search(text)
        if m:
            return STAGE_CODES[(m[1] or m[2]).lower()]
    return None


def documented_ckd_codes(facts: Iterable[ClinicalFact]) -> list[str]:
    """Distinct N18 codes the CKD facts document: N18.6 alone when ESRD is documented,
    N18.9 when CKD is documented without a stage, [] when CKD is not documented."""
    facts = list(facts)
    found = {c for f in facts if (c := documented_stage_code(f)) is not None}
    if "N18.6" in found:
        return ["N18.6"]
    if found:
        return sorted(found)
    return ["N18.9"] if facts else []


def stage5_or_esrd(facts: Iterable[ClinicalFact]) -> bool:
    return any(c in {"N18.5", "N18.6"} for c in documented_ckd_codes(facts))


HF_CODES = frozenset(
    {
        "I50.1",
        "I50.20",
        "I50.21",
        "I50.22",
        "I50.23",
        "I50.30",
        "I50.31",
        "I50.32",
        "I50.33",
        "I50.40",
        "I50.41",
        "I50.42",
        "I50.43",
        "I50.9",
    }
)
_HF_SYSTOLIC = re.compile(r"systolic|reduced ejection|\bhfref\b", re.IGNORECASE)
_HF_DIASTOLIC = re.compile(r"diastolic|preserved ejection|\bhfpef\b", re.IGNORECASE)
_HF_COMBINED = re.compile(
    r"combined|systolic and diastolic|diastolic and systolic", re.IGNORECASE
)
_HF_ACUTE_ON_CHRONIC = re.compile(r"acute[ -]on[ -]chronic", re.IGNORECASE)
_HF_ACUTE = re.compile(r"\bacute\b", re.IGNORECASE)
_HF_CHRONIC = re.compile(r"\bchronic\b", re.IGNORECASE)


def documented_heart_failure_code(fact: ClinicalFact) -> str:
    """I50 code supported by one heart-failure fact; missing axes stay unspecified."""
    text = " ".join([fact.concept, *fact.details.values()])
    if re.search(r"left ventricular failure", text, re.IGNORECASE) and not any(
        p.search(text) for p in (_HF_SYSTOLIC, _HF_DIASTOLIC, _HF_COMBINED)
    ):
        return "I50.1"
    type_digit = (
        "4"
        if _HF_COMBINED.search(text)
        else "2"
        if _HF_SYSTOLIC.search(text)
        else "3"
        if _HF_DIASTOLIC.search(text)
        else None
    )
    if type_digit is None:
        return "I50.9"
    acuity_digit = (
        "3"
        if _HF_ACUTE_ON_CHRONIC.search(text)
        else "1"
        if _HF_ACUTE.search(text)
        else "2"
        if _HF_CHRONIC.search(text)
        else "0"
    )
    return f"I50.{type_digit}{acuity_digit}"


def documented_heart_failure_codes(facts: Iterable[ClinicalFact]) -> list[str]:
    found = {documented_heart_failure_code(f) for f in facts}
    if len(found) > 1:
        found.discard("I50.9")
    return sorted(found)


def heart_failure_additions(
    inp: RuleInput, codes: CodeLookup, rule_id: str, r: RuleResult, facts: list[ClinicalFact]
) -> list[Suggestion]:
    """I50 codes required by I11.0/I13, carrying only their heart-failure facts."""
    present_codes = {s.code for s in active(inp.suggestions) if is_heart_failure(s.code)}
    out = []
    for code in documented_heart_failure_codes(facts):
        if code in present_codes:
            continue
        supporting = [f for f in facts if documented_heart_failure_code(f) == code]
        if not supporting and code == "I50.9":
            supporting = facts
        out.append(added(inp, codes, code, rule_id, [], r, ids_of(supporting)))
    return out


class Conditions:
    """Which of diabetes, CKD, heart failure and hypertension the note documents, and whether
    the presumed links hold (I.A.15, I.C.9.a): not when the condition is `caused_by` a fact
    other than the diabetes (R2) or hypertension (R3-R5)."""

    def __init__(self, inp: RuleInput) -> None:
        self.diabetes = diabetes_facts(inp)
        self.ckd = ckd_facts(inp)
        self.hf = heart_failure_facts(inp)
        self.htn = hypertension_facts(inp)
        htn_ids = ids_of(self.htn)
        self.hf_linked = bool(self.htn and self.hf) and not caused_by_other(
            inp, ids_of(self.hf), htn_ids
        )
        self.ckd_linked = bool(self.htn and self.ckd) and not caused_by_other(
            inp, ids_of(self.ckd), htn_ids
        )


def fail_all(
    suggestions: list[Suggestion], targets: Iterable[Suggestion], r: RuleResult
) -> list[Suggestion]:
    """Keep the targets only as "not suggested", with the reason (outcome fail)."""
    return review_all(suggestions, targets, r)


def settle_variant(
    inp: RuleInput,
    codes: CodeLookup,
    out: list[Suggestion],
    variants: set[str],
    target: str,
    rule_id: str,
    r: RuleResult,
    trigger_ids: list[str],
) -> tuple[list[Suggestion], list[DroppedCode]]:
    """Leave exactly one of mutually exclusive `variants`: `target`. Other selected variants
    are dropped; `target` is added (from the code table) when it is not already there."""
    wrong = [s for s in active(out) if s.code in variants and s.code != target]
    dropped = [
        DroppedCode(
            code=s.code,
            fact_ids=s.fact_ids,
            rule_id=rule_id,
            reason=f"The documented facts call for {target}, not {s.code}.",
        )
        for s in wrong
    ]
    wrong_ids = {s.suggestion_id for s in wrong}
    out = [s for s in out if s.suggestion_id not in wrong_ids]
    if not present(active(out), target):
        ids = sorted({*trigger_ids, *fact_ids(wrong)})
        out.append(added(inp, codes, target, rule_id, wrong, r, ids))
    return out, dropped


def stage_additions(
    inp: RuleInput, codes: CodeLookup, rule_id: str, r: RuleResult, facts: list[ClinicalFact]
) -> list[Suggestion]:
    """N18 codes to add when a CKD combination is coded but no N18 code was selected.

    The combination codes say "use additional code to identify the stage" (Tabular E11.22,
    I12, I13). The stage comes from the CKD facts; no stage gives N18.9, which R9 flags.
    """
    if any(is_ckd(s.code) for s in active(inp.suggestions)) or not facts:
        return []
    documented = documented_ckd_codes(facts)
    out = []
    for code in documented:
        ids = [f.fact_id for f in facts if (documented_stage_code(f) or "N18.9") == code]
        if code == "N18.6" or not ids:
            ids = ids_of(facts)
        out.append(added(inp, codes, code, rule_id, [], r, ids))
    return out
