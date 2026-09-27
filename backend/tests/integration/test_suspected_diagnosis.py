"""Full pipeline, outpatient uncertain diagnosis (IV.H; Codex finding 12): "possible heart
failure" is not coded; the documented symptom is."""

import json
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.models import ExtractionOutput, Note, SelectionOutput
from app.pipeline.graph import run_pipeline
from app.pipeline.state import PipelineDeps
from app.segment.segmenter import segment_note
from app.terminology.code_sets import resolve_code_sets
from tests.fakes import ScriptedLlm
from tests.integration.conftest import FakeEmbedder

GOLD = json.loads(
    (Path(__file__).parents[3] / "data" / "gold_notes" / "n015.json").read_text()
)  # synthetic


def _n(sentences: list[str], startswith: str) -> int:
    return next(i + 1 for i, s in enumerate(sentences) if s.startswith(startswith))


def test_possible_heart_failure_is_not_coded_but_the_symptom_is(seeded: Engine) -> None:
    sentences = segment_note(GOLD["text"])
    texts = [s.text for s in sentences]
    sob, known_htn = _n(texts, "Reports shortness of breath"), _n(texts, "Known hypertension")
    possible_hf, htn = _n(texts, "Possible heart failure"), _n(texts, "Essential hypertension")
    extract = ExtractionOutput.model_validate(
        {
            "facts": [
                {"fact_id": "f1", "kind": "condition", "concept": "heart failure",
                 "status": "suspected", "details": {}, "links": [], "evidence": [possible_hf]},
                {"fact_id": "f2", "kind": "condition", "concept": "shortness of breath",
                 "status": "active", "details": {}, "links": [], "evidence": [sob]},
                {"fact_id": "f3", "kind": "condition", "concept": "essential hypertension",
                 "status": "active", "details": {}, "links": [], "evidence": [known_htn, htn]},
            ],
            "mdm": {"problems": None, "data": None, "risk": None, "evidence": []},
        }
    )  # fmt: skip
    select = SelectionOutput.model_validate(
        {
            "selections": [
                # The model wrongly codes the suspected diagnosis; it has no candidates.
                {"fact_id": "f1", "code": "I50.9", "evidence": [possible_hf], "rationale": "r"},
                {"fact_id": "f2", "code": "R06.02", "evidence": [sob], "rationale": "r"},
                {"fact_id": "f3", "code": "I10", "evidence": [htn], "rationale": "r"},
            ]
        }
    )
    note = Note(
        id=str(uuid.uuid4()),
        visit_date=date.fromisoformat(GOLD["visit_date"]),
        patient_type=GOLD["patient_type"],
        text=GOLD["text"],
        sentences=sentences,
        parent_note_id=None,
        created_at=datetime.now(UTC),
    )
    with Session(seeded) as s:
        deps = PipelineDeps(s, ScriptedLlm(extract=extract, select=select), FakeEmbedder())
        result = run_pipeline(deps, note, resolve_code_sets(s, note.visit_date))

    assert result.status == "completed"
    codes = sorted(x.code for x in result.suggestions)
    assert not [c for c in codes if c.startswith("I50")]
    assert codes == ["I10", "R06.02"]
    assert result.model_errors == 1  # the I50.9 selection was dropped
    by_code = {x.code: x for x in result.suggestions}
    assert by_code["R06.02"].evidence == [sob]
