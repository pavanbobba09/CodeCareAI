import json
from typing import Any

from app.llm.prompts import load_prompt
from app.models import ExtractionOutput
from app.pipeline.nodes import Node
from app.pipeline.state import PipelineDeps, PipelineState
from app.pipeline.validate import validate_facts


def make(deps: PipelineDeps) -> Node:
    system = load_prompt(deps.extract_prompt, ExtractionOutput)

    def extract_facts(state: PipelineState) -> dict[str, Any]:
        user = json.dumps(
            {
                "patient_type": state.note.patient_type,
                "sentences": [
                    {"n": s.n, "section": s.section, "text": s.text} for s in state.note.sentences
                ],
            }
        )
        out = deps.llm.complete_json("extract", system, user, ExtractionOutput, state.deadline)
        facts, errors = validate_facts(out.facts, {s.n for s in state.note.sentences})
        return {"facts": facts, "mdm": out.mdm, "model_errors": state.model_errors + errors}

    return extract_facts
