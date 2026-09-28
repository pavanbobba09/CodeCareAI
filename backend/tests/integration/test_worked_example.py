"""M2 done-when: the worked example, replayed from real recorded LLM responses."""

import json
from pathlib import Path

import pytest
from sqlalchemy import Engine

from app.llm.replay import ReplayLlm
from tests.integration.test_pipeline_api import WORKED, _client, _create_note

pytestmark = pytest.mark.integration

RECORDING = Path(__file__).parents[1] / "fixtures" / "llm" / "worked_example"


def test_worked_example_from_recorded_llm(seeded: Engine) -> None:
    llm = ReplayLlm(RECORDING)
    client = _client(seeded, llm)
    note = _create_note(client)

    resp = client.post(f"/api/v1/notes/{note['id']}/analyze")

    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["status"] == "completed"
    assert result["model_errors"] == 0
    assert sorted((s["code"], s["evidence"]) for s in result["suggestions"]) == sorted(
        (e["code"], e["evidence"]) for e in WORKED["expected"]
    )
    # The model's E11.22 cites only the diabetes fact; R2 must attach the CKD fact, not fail it.
    e11_22 = next(s for s in result["suggestions"] if s["code"] == "E11.22")
    assert e11_22["confidence"] != "not_suggested"
    # The extract prompt depends only on the note, so it must match the recording exactly.
    # (The select prompt differs here because the fixture db has fewer candidates.)
    assert "extract" not in llm.prompt_drift


def test_recording_is_from_one_model() -> None:
    models = {json.loads(p.read_text())["model"] for p in RECORDING.glob("*.json")}
    assert len(models) == 1
