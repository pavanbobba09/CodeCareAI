"""API and pipeline contract types from DESIGN.md §5.1. Names must match the design exactly."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

CodeSystem = Literal["ICD-10-CM", "CPT"]
PatientType = Literal["new", "established"]
FactKind = Literal["condition", "procedure", "medication"]
FactStatus = Literal[
    "active", "history", "ruled_out", "denied", "suspected", "performed", "planned"
]
Confidence = Literal["strong", "review", "not_suggested"]
ReviewAction = Literal["accept", "edit", "reject"]
MdmLevel = Literal["straightforward", "low", "moderate", "high"]
CandidateSource = Literal["abbreviation", "index", "text", "vector"]
PipelineErrorCode = Literal[
    "LLM_UNAVAILABLE", "LLM_BAD_OUTPUT", "TIMEOUT", "CODE_SET_MISSING", "DB_ERROR", "PIPELINE_ERROR"
]


class Sentence(BaseModel):
    n: int  # 1-based number within the note
    section: str  # normalized note section
    text: str  # exact sentence text
    start: int  # inclusive offset in Note.text
    end: int  # exclusive offset in Note.text


class NoteCreate(BaseModel):
    visit_date: date  # selects the effective code release
    patient_type: PatientType  # selects new/established E/M range
    text: str = Field(min_length=20, max_length=20_000)
    parent_note_id: str | None = None  # prior version, if revised


class Note(BaseModel):
    id: str
    visit_date: date
    patient_type: PatientType
    text: str
    sentences: list[Sentence]
    parent_note_id: str | None
    created_at: datetime


class FactLink(BaseModel):
    type: Literal["caused_by", "associated_with"]
    target_fact_id: str


class ClinicalFact(BaseModel):
    fact_id: str
    kind: FactKind
    concept: str  # normalized clinical term
    status: FactStatus
    details: dict[str, str]  # stage, type, acuity, laterality, drug, etc.
    links: list[FactLink]
    evidence: list[int]  # supporting Sentence.n values


class MdmElements(BaseModel):
    problems: MdmLevel | None
    data: MdmLevel | None
    risk: MdmLevel | None
    evidence: list[int]


class ExtractionOutput(BaseModel):
    facts: list[ClinicalFact]
    mdm: MdmElements


class CodeCandidate(BaseModel):
    code: str
    system: CodeSystem
    description: str  # official ICD text or project-written CPT label
    score: float
    sources: list[CandidateSource]


class CandidateSet(BaseModel):
    fact_id: str
    candidates: list[CodeCandidate]  # maximum 20


class CodeSelection(BaseModel):
    fact_id: str
    code: str | None  # must belong to this fact's CandidateSet
    evidence: list[int]
    rationale: str = Field(max_length=300)


class SelectionOutput(BaseModel):
    """LLM call 2 response. JSON mode needs an object at the root, so the list is wrapped."""

    selections: list[CodeSelection]


class RuleResult(BaseModel):
    rule_id: str  # R1 through R14
    outcome: Literal["pass", "fail", "needs_review"]
    message: str
    source_ref: str  # guideline/table source identifier
    affects_codes: list[str]


class Gap(BaseModel):
    gap_id: str
    kind: Literal["missing", "ambiguous", "conflicting", "unsupported"]
    missing: str
    affects_codes: list[str]
    rule_id: str | None
    query_text: str  # neutral; must not lead toward higher payment
    severity: Literal["blocking", "review", "info"]


class EmResult(BaseModel):
    code: str | None
    mdm_level: MdmLevel | None
    missing: list[str]


class Suggestion(BaseModel):
    suggestion_id: str
    code: str
    system: CodeSystem
    description: str
    fact_ids: list[str]
    evidence: list[int]
    rule_results: list[RuleResult]
    gap_ids: list[str]
    confidence: Confidence
    added_by_rule: str | None = None  # rule id when a rule added the code (e.g. "R3")


class CodeSetSelection(BaseModel):
    icd10cm: str  # e.g. ICD10CM-FY2027
    cpt: str | None  # e.g. CPT-DEMO-2026; None when no CPT set covers the visit date


class PipelineError(BaseModel):
    code: PipelineErrorCode
    stage: str
    message: str


class AnalysisResult(BaseModel):
    analysis_id: str
    note_id: str
    status: Literal["completed", "failed"]
    code_sets: CodeSetSelection
    facts: list[ClinicalFact]
    suggestions: list[Suggestion]
    gaps: list[Gap]
    em: EmResult | None
    model: str
    prompt_version: str
    model_errors: int
    latency_ms: int
    error: PipelineError | None
    created_at: datetime


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    analysis_id: str | None = None


class HealthResponse(BaseModel):
    service: Literal["codecare-api"]
    db: bool
    code_sets: list[str]  # loaded CodeSet ids, e.g. ICD10CM-FY2027
