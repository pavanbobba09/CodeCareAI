"""Rule-based evidence support check (Codex finding 8). Pure: no db, no LLM.

A predicted code is supported when its cited sentences:
1. name the condition: every content word of the code description or of one of its
   Alphabetic Index paths appears (after abbreviation expansion). Combination codes need
   each part named instead (E1x.22: diabetes + CKD; I12: hypertension + CKD; I11.0:
   hypertension + heart failure; I13.0/I13.2: all three). Z79 drug codes need a drug of
   the right class (the R8 drug list);
2. are not negated: a sentence where a negation cue comes before the condition ("no",
   "denies", "negative for", ...) or that says it was ruled out does not count;
3. carry the details the code needs (for example "3b" for N18.32, "systolic" and "chronic"
   for I50.22, "type 1" for E10);
4. come from an active fact, when the code's facts are known (the pipeline; the LLM-only
   baseline has no facts, so this part is skipped there).

This is a deterministic proxy for "the note supports this code", not a coder's judgment.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass

from app.rules.common import (
    CKD_TEXT,
    DIABETES_TEXT,
    ESRD_TEXT,
    HEART_FAILURE_TEXT,
    HYPERTENSION_TEXT,
)
from app.rules.r8_diabetes_drugs import drug_class
from app.terminology.abbreviations import expand

_WORD = re.compile(r"[a-z0-9]+")
_PARENS = re.compile(r"\([^)]*\)")
# Words an Index path or description needs only for grammar or structure.
_STOP = {
    "with", "without", "and", "or", "of", "the", "in", "a", "an", "to", "due", "by", "on",
    "for", "stage", "unspecified", "nos", "other", "specified", "type", "mellitus", "see",
    "current", "long", "term", "use", "through", "classified", "elsewhere", "disease",
    "diseased", "disorder",
}  # fmt: skip
_NEGATION_BEFORE = re.compile(
    r"\b(no|not|denies|denied|without|negative for|free of|absence of|rule out|r/o)\b"
)
_NEGATION_ANYWHERE = re.compile(r"\b(ruled out|was excluded|is excluded|not present)\b")
_NON_ACTIVE = re.compile(
    r"\b(history of|historical|possible|possibly|probable|probably|suspected|"
    r"uncertain|questionable|may have|might have|cannot rule out|could be)\b"
)
_CLAUSE_BOUNDARY = re.compile(r"[;.\n]|\b(?:but|however|although|yet)\b", re.IGNORECASE)

_PARTS: dict[str, list[re.Pattern[str]]] = {
    "22": [DIABETES_TEXT, CKD_TEXT],  # E08-E13 .22
    "I12": [HYPERTENSION_TEXT, CKD_TEXT],
    "I11.0": [HYPERTENSION_TEXT, HEART_FAILURE_TEXT],
    "I13.0": [HYPERTENSION_TEXT, HEART_FAILURE_TEXT, CKD_TEXT],
    "I13.2": [HYPERTENSION_TEXT, HEART_FAILURE_TEXT, CKD_TEXT],
    "I13.1": [HYPERTENSION_TEXT, CKD_TEXT],
}
_DRUG_CLASS = {"Z79.4": "insulin", "Z79.84": "oral", "Z79.85": "injectable_non_insulin"}

_HF_TYPE = {
    "2": re.compile(r"systolic|reduced ejection|hfref"),
    "3": re.compile(r"diastolic|preserved ejection|hfpef"),
    "4": re.compile(r"combined|systolic and diastolic|diastolic and systolic"),
}
_HF_ACUITY = {
    "1": re.compile(r"\bacute\b(?! on chronic)"),
    "2": re.compile(r"(?<!acute on )\bchronic\b"),
    "3": re.compile(r"acute on chronic"),
}
_CKD_STAGE = {
    "N18.1": r"\b(?:stage|stg)\s*1\b",
    "N18.2": r"\b(?:stage|stg)\s*2\b",
    "N18.30": r"\b(?:stage|stg)\s*3\b",
    "N18.31": r"\b(?:stage|stg)\s*3a\b|\b3a\b",
    "N18.32": r"\b(?:stage|stg)\s*3b\b|\b3b\b",
    "N18.4": r"\b(?:stage|stg)\s*4\b",
    "N18.5": r"\b(?:stage|stg)\s*5\b",
}


@dataclass(frozen=True)
class SupportContext:
    """What the checker knows about one code, loaded from the code tables."""

    description: str
    index_paths: list[str]
    abbreviations: Mapping[str, str]


def _words(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def _term_words(term: str, first_segment: bool) -> set[str]:
    text = _PARENS.sub(" ", term)
    if first_segment:
        text = text.split(",")[0]  # "Diabetes, diabetic" -> "Diabetes"
    return {w for w in _words(text) if w not in _STOP}


def _path_words(path: str) -> set[str]:
    path = path.split(" (see ")[0]
    words: set[str] = set()
    for i, segment in enumerate(path.split(" > ")):
        words |= _term_words(segment, first_segment=i == 0)
    return words


def _has(words: list[str], wanted: str) -> bool:
    """Whole word, or a prefix of a text word for longer words (short -> shortness)."""
    return any(w == wanted or (len(wanted) >= 4 and w.startswith(wanted)) for w in words)


def _clause(sentence: str, start: int | None) -> tuple[str, int | None]:
    """The semicolon/sentence/contrast clause containing the named condition."""
    if start is None:
        return sentence, None
    boundaries = list(_CLAUSE_BOUNDARY.finditer(sentence))
    left = max((m.end() for m in boundaries if m.end() <= start), default=0)
    right = min((m.start() for m in boundaries if m.start() > start), default=len(sentence))
    return sentence[left:right], start - left


def _negated(sentence: str, start: int | None) -> bool:
    """A cue scoped to the clause containing the named condition."""
    sentence, start = _clause(sentence, start)
    lowered = sentence.lower()
    if _NEGATION_ANYWHERE.search(lowered) or _NON_ACTIVE.search(lowered):
        return True
    return start is not None and bool(_NEGATION_BEFORE.search(lowered[:start]))


def _start(sentence: str, code: str, term: set[str]) -> int | None:
    """Character position where the condition is first mentioned in the sentence."""
    lowered = sentence.lower()
    starts = [m.start() for p in _parts(code) if (m := p.search(sentence))]
    starts += [m.start() for t in term if (m := re.search(rf"\b{re.escape(t)}", lowered))]
    return min(starts) if starts else None


_STAGE_WORD = re.compile(r"^\d+[ab]?$")  # "2" in "type 2", "3b", "5"


def _detail_words(code: str) -> set[str]:
    if code.startswith("I50"):
        return {"acute", "chronic", "systolic", "diastolic", "combined", "congestive"}
    if code.endswith(".65"):
        return {"hyperglycemia", "controlled", "inadequately", "poorly", "uncontrolled", "out"}
    return set()


def _parts(code: str) -> list[re.Pattern[str]]:
    if code.endswith(".22") and code[:3] in {"E08", "E09", "E10", "E11", "E13"}:
        return _PARTS["22"]
    return next((p for key, p in _PARTS.items() if key != "22" and code.startswith(key)), [])


def _names(text: str, code: str, ctx: SupportContext) -> tuple[bool, set[str]]:
    """Does the text name the code's condition? Returns (named, words that named it)."""
    words = _words(text)
    parts = _parts(code)
    if parts:
        return all(p.search(text) for p in parts), set()
    if code in _DRUG_CLASS:
        return drug_class(text) == _DRUG_CLASS[code], set()
    terms = [_term_words(ctx.description, first_segment=False)]
    terms += [_path_words(p) for p in ctx.index_paths]
    # Details are judged by _missing_detail, not here: "3b", "acute", "hyperglycemia", ...
    details = _detail_words(code)
    terms = [{w for w in t if w not in details and not _STAGE_WORD.match(w)} for t in terms]
    for term in terms:
        if term and all(_has(words, t) for t in term):
            return True, term
    return False, set()


def _missing_detail(code: str, text: str) -> str | None:
    lowered = text.lower()
    if code in _CKD_STAGE and not re.search(_CKD_STAGE[code], lowered):
        return f"CKD stage for {code}"
    if code in {"N18.6", "I12.0", "I13.2"} and not (
        ESRD_TEXT.search(lowered) or re.search(r"\b(?:stage|stg)\s*5\b", lowered)
    ):
        return "stage 5 or ESRD"
    if code.startswith("I50.") and len(code) >= 5 and code[4] in _HF_TYPE:
        if not _HF_TYPE[code[4]].search(lowered):
            return "heart failure type"
        if len(code) == 6 and code[5] in _HF_ACUITY and not _HF_ACUITY[code[5]].search(lowered):
            return "heart failure acuity"
    if code.startswith("E10") and not re.search(r"type\s*(1|i|one)\b|\bt1dm\b|\bdm1\b", lowered):
        return "diabetes type 1"
    if code.startswith("E11") and re.search(
        r"type\s*(1|i|one)\b|\bt1dm\b|\bdm1\b|\biddm\b", lowered
    ):
        return "diabetes type does not match E11"
    if code == "E11.65" and not re.search(
        r"hyperglyc|poorly controlled|uncontrolled|out of control|inadequately controlled",
        lowered,
    ):
        return "hyperglycemia or poor control"
    return None


def check_support(
    code: str, cited: list[str], ctx: SupportContext, fact_statuses: list[str] | None
) -> tuple[bool, str]:
    """(supported, reason) for one predicted code and the sentences it cites."""
    if fact_statuses is not None and not {"active", "performed"} & set(fact_statuses):
        return False, "no active fact"
    expanded = [expand(s, ctx.abbreviations)[0] for s in cited]
    named, _ = _names(" ".join(expanded), code, ctx)
    if not named:
        return False, "condition not named in the cited sentences"
    kept = []
    for sentence in expanded:
        _, term = _names(sentence, code, ctx)
        if not _negated(sentence, _start(sentence, code, term)):
            kept.append(sentence)
    text = " ".join(kept)
    if not _names(text, code, ctx)[0]:
        return False, "negated"
    missing = _missing_detail(code, text)
    if missing:
        return False, f"missing detail: {missing}"
    return True, "supported"
