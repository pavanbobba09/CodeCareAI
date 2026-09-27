"""PipelineState: the only thing nodes read and write (CLAUDE.md code conventions)."""

from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.llm.client import JsonLlm
from app.models import (
    AnalysisResult,
    CandidateSet,
    ClinicalFact,
    CodeSelection,
    CodeSetSelection,
    Gap,
    MdmElements,
    Note,
    PipelineError,
    Suggestion,
)
from app.terminology.embedder import Embedder

PROMPT_VERSION = "extract_v1+select_v1"
ANALYSIS_TIME_LIMIT_S = 150.0


class PipelineState(BaseModel):
    analysis_id: str
    note: Note
    code_sets: CodeSetSelection
    started_at: datetime
    started_monotonic: float
    deadline: float  # monotonic clock; see ANALYSIS_TIME_LIMIT_S

    facts: list[ClinicalFact] = []
    mdm: MdmElements | None = None
    candidate_sets: list[CandidateSet] = []
    selections: list[CodeSelection] = []
    suggestions: list[Suggestion] = []
    gaps: list[Gap] = []
    model_errors: int = 0
    error: PipelineError | None = None
    result: AnalysisResult | None = None


@dataclass(frozen=True)
class PipelineDeps:
    """Services nodes call. Passed by closure, never stored in state."""

    session: Session
    llm: JsonLlm
    embedder: Embedder
