from typing import Any

from app.models import AnalysisResult
from app.pipeline.nodes import Node
from app.pipeline.nodes.assemble import latency_ms
from app.pipeline.state import PROMPT_VERSION, PipelineDeps, PipelineState


def make(deps: PipelineDeps, clock: Any) -> Node:
    def fail(state: PipelineState) -> dict[str, Any]:
        # No partial results: a failed analysis carries only the error (DESIGN.md §4.4).
        return {
            "result": AnalysisResult(
                analysis_id=state.analysis_id,
                note_id=state.note.id,
                status="failed",
                code_sets=state.code_sets,
                facts=[],
                suggestions=[],
                gaps=[],
                em=None,
                model=deps.llm.model,
                prompt_version=PROMPT_VERSION,
                model_errors=state.model_errors,
                latency_ms=latency_ms(state, clock()),
                error=state.error,
                created_at=state.started_at,
            )
        }

    return fail
