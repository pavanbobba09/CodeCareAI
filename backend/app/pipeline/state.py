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

EXTRACT_PROMPT = "extract_v2"  # default; the eval can run an older version (--extract-prompt)
SELECT_PROMPT = "select_v1"


def prompt_version(extract_prompt: str = EXTRACT_PROMPT) -> str:
    return f"{extract_prompt}+{SELECT_PROMPT}"


PROMPT_VERSION = prompt_version()
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
    rule_model_errors: int = 0  # the part of model_errors added by run_rules (R1 on LLM picks)
    error: PipelineError | None = None
    result: AnalysisResult | None = None


class SavedLlmOutputs(BaseModel):
    """What the LLM steps produced for one note, kept so rules can be replayed offline.

    `model_errors` counts what extract/select validation dropped before the rules ran.
    """

    facts: list[ClinicalFact]
    candidate_sets: list[CandidateSet]
    selections: list[CodeSelection]
    model_errors: int


@dataclass(frozen=True)
class PipelineDeps:
    """Services nodes call. Passed by closure, never stored in state."""

    session: Session
    llm: JsonLlm
    embedder: Embedder
    extract_prompt: str = EXTRACT_PROMPT
