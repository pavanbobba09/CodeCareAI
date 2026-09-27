"""API contract types from DESIGN.md §5.1. Names must match the design exactly."""

from typing import Literal

from pydantic import BaseModel

CodeSystem = Literal["ICD-10-CM", "CPT"]
FactKind = Literal["condition", "procedure", "medication"]
FactStatus = Literal[
    "active", "history", "ruled_out", "denied", "suspected", "performed", "planned"
]
CandidateSource = Literal["abbreviation", "index", "text", "vector"]


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


class CodeCandidate(BaseModel):
    code: str
    system: CodeSystem
    description: str  # official ICD text or project-written CPT label
    score: float
    sources: list[CandidateSource]


class CandidateSet(BaseModel):
    fact_id: str
    candidates: list[CodeCandidate]  # maximum 20


class CodeSetSelection(BaseModel):
    icd10cm: str  # e.g. ICD10CM-FY2027
    cpt: str  # e.g. CPT-DEMO-2026


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    analysis_id: str | None = None


class HealthResponse(BaseModel):
    service: Literal["codecare-api"]
    db: bool
    code_sets: list[str]  # loaded CodeSet ids, e.g. ICD10CM-FY2027
