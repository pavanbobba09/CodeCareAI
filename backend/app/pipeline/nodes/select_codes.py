import json
from typing import Any

from app.llm.prompts import load_prompt
from app.models import SelectionOutput
from app.pipeline.nodes import Node
from app.pipeline.state import PipelineDeps, PipelineState
from app.pipeline.validate import validate_selections


def make(deps: PipelineDeps) -> Node:
    system = load_prompt("select_v1", SelectionOutput)

    def select_codes(state: PipelineState) -> dict[str, Any]:
        if not state.candidate_sets:
            return {"selections": []}
        sentences = {s.n: s.text for s in state.note.sentences}
        facts = {f.fact_id: f for f in state.facts}
        user = json.dumps(
            {
                "facts": [
                    {
                        "fact_id": cs.fact_id,
                        "concept": facts[cs.fact_id].concept,
                        "status": facts[cs.fact_id].status,
                        "details": facts[cs.fact_id].details,
                        "sentences": [
                            {"n": n, "text": sentences[n]} for n in facts[cs.fact_id].evidence
                        ],
                        "candidates": [
                            {"code": c.code, "description": c.description} for c in cs.candidates
                        ],
                    }
                    for cs in state.candidate_sets
                ]
            }
        )
        out = deps.llm.complete_json("select", system, user, SelectionOutput, state.deadline)
        selections, errors = validate_selections(
            out.selections, state.candidate_sets, set(sentences)
        )
        return {"selections": selections, "model_errors": state.model_errors + errors}

    return select_codes
