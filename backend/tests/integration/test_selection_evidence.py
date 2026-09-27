"""A code may only cite sentences its fact cites (Codex finding 7)."""

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.pipeline.graph import run_pipeline
from app.pipeline.state import PipelineDeps
from tests.fakes import ScriptedLlm
from tests.integration.conftest import FakeEmbedder
from tests.integration.test_pipeline_api import EXTRACT, SELECT, _note_and_sets


def test_selection_citing_a_sentence_outside_its_fact_is_dropped(seeded: Engine) -> None:
    note, sets = _note_and_sets(seeded)
    assert [f.evidence for f in EXTRACT.facts] == [[1], [1]]
    select = SELECT.model_copy(deep=True)
    # Sentence 2 is real ("62-year-old presents ...") but no fact cites it for E11.22.
    select.selections[0] = select.selections[0].model_copy(update={"evidence": [1, 2]})
    with Session(seeded) as s:
        deps = PipelineDeps(s, ScriptedLlm(extract=EXTRACT, select=select), FakeEmbedder())
        result = run_pipeline(deps, note, sets)

    assert [x.code for x in result.suggestions if x.code.startswith("E11")] == []
    assert result.model_errors == 1
