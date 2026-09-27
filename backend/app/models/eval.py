"""Evaluation types (DESIGN.md §5.4)."""

from datetime import date

from pydantic import BaseModel

from app.models.core import CodeSystem, PatientType


class ExpectedCode(BaseModel):
    code: str
    system: CodeSystem
    reason: str  # one line: which guideline or note sentence justifies this code


class GoldNote(BaseModel):  # one file per note: data/gold_notes/n001.json
    note_id: str  # "n001"
    visit_date: date
    patient_type: PatientType
    text: str
    expected_codes: list[ExpectedCode]
    expected_gap_rules: list[str]  # rule ids that must raise a gap, e.g. ["R9"]
    expected_em: str | None  # None until M6
    tags: list[str]  # e.g. ["negation", "htn+ckd", "abbrev"]


class BaselineCode(BaseModel):
    code: str
    evidence: list[int]
    rationale: str


class BaselineOutput(BaseModel):
    """LLM-only baseline response: codes straight from the note, no candidates, no rules."""

    codes: list[BaselineCode]
