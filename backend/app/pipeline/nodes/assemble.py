from typing import Any

from app.models import AnalysisResult
from app.pipeline.confidence import finalize
from app.pipeline.nodes import Node
from app.pipeline.state import PipelineDeps, PipelineState, prompt_version


def latency_ms(state: PipelineState, now: float) -> int:
    return int((now - state.started_monotonic) * 1000)


def make(deps: PipelineDeps, clock: Any) -> Node:
    def assemble(state: PipelineState) -> dict[str, Any]:
        suggestions, gaps = finalize(state.suggestions, state.gaps)
        return {
            "result": AnalysisResult(
                analysis_id=state.analysis_id,
                note_id=state.note.id,
                status="completed",
                code_sets=state.code_sets,
                facts=state.facts,
                suggestions=suggestions,
                gaps=gaps,
                em=None,  # E/M arrives in M6
                model=deps.llm.model,
                prompt_version=prompt_version(deps.extract_prompt),
                model_errors=state.model_errors,
                latency_ms=latency_ms(state, clock()),
                error=None,
                created_at=state.started_at,
            )
        }

    return assemble
