"""What a run stores per note. Enough to re-score without the db or the LLM (CI)."""

from typing import Literal

from pydantic import BaseModel

from app.llm.client import CallUsage
from app.pipeline.state import SavedLlmOutputs

Setup = Literal["pipeline", "baseline"]


class PredictedCode(BaseModel):
    code: str
    evidence: list[int]
    in_code_set: bool  # False = invented: not in the code set for the visit date
    billable: bool
    supported: bool | None = None  # eval/support.py; None for runs saved before the check
    support_reason: str | None = None


class NoteRun(BaseModel):
    note_id: str
    setup: Setup
    model: str
    prompt_version: str
    status: Literal["completed", "failed"]
    error: str | None  # PipelineError code, e.g. "LLM_UNAVAILABLE"
    attempts: int
    n_sentences: int
    predicted: list[PredictedCode]
    gap_rules: list[str]
    em_code: str | None
    model_errors: int
    latency_ms: int
    usage: list[CallUsage] = []  # every LLM call for this note, across retry attempts
    llm_outputs: SavedLlmOutputs | None = None  # pipeline only; what replay reruns rules on
