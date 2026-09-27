from typing import Any

from app.pipeline.nodes import Node
from app.pipeline.state import PipelineDeps, PipelineState
from app.terminology.search import search_candidates

# Only facts that can be coded at this visit get candidates (DESIGN.md §4.1 step 6).
CODABLE_STATUSES = {"active", "performed"}


def make(deps: PipelineDeps) -> Node:
    def retrieve_candidates(state: PipelineState) -> dict[str, Any]:
        sets = [
            search_candidates(deps.session, fact, state.code_sets, deps.embedder)
            for fact in state.facts
            if fact.status in CODABLE_STATUSES
        ]
        return {"candidate_sets": [cs for cs in sets if cs.candidates]}

    return retrieve_candidates
