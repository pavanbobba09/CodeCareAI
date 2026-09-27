"""Linear LangGraph pipeline with one failure branch (CLAUDE.md rule 11).

extract_facts -> retrieve_candidates -> select_codes -> run_rules -> assemble
Any node that sets `error` routes to `fail`. No loops, no checkpointer, no agents.
"""

import logging
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.llm.client import LlmError
from app.models import AnalysisResult, CodeSetSelection, Note, PipelineError
from app.pipeline.nodes import (
    Node,
    assemble,
    extract_facts,
    fail,
    retrieve_candidates,
    run_rules,
    select_codes,
)
from app.pipeline.state import ANALYSIS_TIME_LIMIT_S, PipelineDeps, PipelineState

log = logging.getLogger(__name__)

STEPS = ["extract_facts", "retrieve_candidates", "select_codes", "run_rules"]


def _guard(stage: str, node: Node, clock: Callable[[], float]) -> Node:
    """Turn deadline overruns and exceptions into PipelineState.error."""

    def guarded(state: PipelineState) -> dict[str, Any]:
        if clock() > state.deadline:
            return {
                "error": PipelineError(code="TIMEOUT", stage=stage, message="Time limit reached.")
            }
        try:
            return node(state)
        except LlmError as exc:
            return {"error": PipelineError(code=exc.code, stage=stage, message=exc.message)}
        except Exception as exc:
            log.exception("pipeline stage %s failed", stage)
            return {
                "error": PipelineError(
                    code="PIPELINE_ERROR", stage=stage, message=f"{type(exc).__name__} in {stage}."
                )
            }

    return guarded


def build_graph(deps: PipelineDeps, clock: Callable[[], float] = time.monotonic) -> Any:
    nodes: dict[str, Node] = {
        "extract_facts": extract_facts.make(deps),
        "retrieve_candidates": retrieve_candidates.make(deps),
        "select_codes": select_codes.make(deps),
        "run_rules": run_rules.make(deps),
    }
    graph = StateGraph(PipelineState)
    for name in STEPS:
        graph.add_node(name, _guard(name, nodes[name], clock))
    graph.add_node("assemble", assemble.make(deps, clock))
    graph.add_node("fail", fail.make(deps, clock))

    graph.add_edge(START, STEPS[0])
    for name, nxt in zip(STEPS, [*STEPS[1:], "assemble"], strict=True):
        graph.add_conditional_edges(
            name, lambda s, nxt=nxt: "fail" if s.error else nxt, [nxt, "fail"]
        )
    graph.add_edge("assemble", END)
    graph.add_edge("fail", END)
    return graph.compile()


def run_pipeline(
    deps: PipelineDeps,
    note: Note,
    code_sets: CodeSetSelection,
    clock: Callable[[], float] = time.monotonic,
) -> AnalysisResult:
    now = clock()
    state = PipelineState(
        analysis_id=str(uuid.uuid4()),
        note=note,
        code_sets=code_sets,
        started_at=datetime.now(UTC),
        started_monotonic=now,
        deadline=now + ANALYSIS_TIME_LIMIT_S,
    )
    out = build_graph(deps, clock).invoke(state)
    result = out["result"]
    assert isinstance(result, AnalysisResult)
    return result
