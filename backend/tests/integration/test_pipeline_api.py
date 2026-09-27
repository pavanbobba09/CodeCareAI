"""Pipeline and API behaviour on the fixture db with a scripted (not recorded) LLM."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.api.deps import get_embedder, get_llm
from app.config import get_settings
from app.db import repo
from app.db.models import AnalysisRow
from app.db.session import get_session
from app.llm.client import JsonLlm, LlmError
from app.main import app
from app.models import ExtractionOutput, SelectionOutput
from app.pipeline.graph import run_pipeline
from app.pipeline.state import PipelineDeps
from app.terminology.code_sets import resolve_code_sets
from app.terminology.embedder import Embedder
from tests.fakes import ScriptedLlm
from tests.integration.conftest import FakeEmbedder

pytestmark = pytest.mark.integration

WORKED = json.loads(
    (Path(__file__).parents[3] / "data" / "examples" / "worked_example.json").read_text()
)

EXTRACT = ExtractionOutput.model_validate(
    {
        "facts": [
            {
                "fact_id": "f1",
                "kind": "condition",
                "concept": "type 2 diabetes mellitus",
                "status": "active",
                "details": {"type": "2"},
                "links": [{"type": "associated_with", "target_fact_id": "f2"}],
                "evidence": [1],
            },
            {
                "fact_id": "f2",
                "kind": "condition",
                "concept": "chronic kidney disease",
                "status": "active",
                "details": {"stage": "3"},
                "links": [],
                "evidence": [1],
            },
        ],
        "mdm": {"problems": None, "data": None, "risk": None, "evidence": []},
    }
)
SELECT = SelectionOutput.model_validate(
    {
        "selections": [
            {"fact_id": "f1", "code": "E11.22", "evidence": [1], "rationale": "DM2 with CKD."},
            {"fact_id": "f2", "code": "N18.30", "evidence": [1], "rationale": "CKD stage 3."},
        ]
    }
)


class BrokenEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embedder down")


def _client(seeded: Engine, llm: JsonLlm, embedder: Embedder | None = None) -> TestClient:
    def session() -> Iterator[Session]:
        with Session(seeded) as s:
            yield s

    app.dependency_overrides[get_session] = session
    app.dependency_overrides[get_llm] = lambda: llm
    app.dependency_overrides[get_embedder] = lambda: embedder or FakeEmbedder()
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides() -> Iterator[None]:
    yield
    app.dependency_overrides.clear()


def _create_note(client: TestClient, **overrides: Any) -> dict[str, Any]:
    resp = client.post("/api/v1/notes", json={**WORKED["note"], **overrides})
    assert resp.status_code == 201, resp.text
    body: dict[str, Any] = resp.json()
    return body


def test_create_and_read_note(seeded: Engine) -> None:
    client = _client(seeded, ScriptedLlm())
    note = _create_note(client)

    assert note["sentences"][0]["text"] == (
        "Type 2 diabetes mellitus with chronic kidney disease stage 3."
    )
    assert client.get(f"/api/v1/notes/{note['id']}").json() == note


def test_note_errors(seeded: Engine) -> None:
    client = _client(seeded, ScriptedLlm())

    short = client.post("/api/v1/notes", json={**WORKED["note"], "text": "too short"})
    assert (short.status_code, short.json()["error_code"]) == (422, "VALIDATION_ERROR")

    orphan = client.post("/api/v1/notes", json={**WORKED["note"], "parent_note_id": "nope"})
    assert (orphan.status_code, orphan.json()["error_code"]) == (404, "PARENT_NOTE_NOT_FOUND")

    missing = client.get("/api/v1/notes/nope")
    assert (missing.status_code, missing.json()["error_code"]) == (404, "NOTE_NOT_FOUND")

    analyze = client.post("/api/v1/notes/nope/analyze")
    assert (analyze.status_code, analyze.json()["error_code"]) == (404, "NOTE_NOT_FOUND")


def test_revised_note_links_to_parent(seeded: Engine) -> None:
    client = _client(seeded, ScriptedLlm())
    parent = _create_note(client)
    child = _create_note(client, parent_note_id=parent["id"])
    assert child["parent_note_id"] == parent["id"]


def test_analyze_worked_example_with_scripted_llm(seeded: Engine) -> None:
    llm = ScriptedLlm(extract=EXTRACT, select=SELECT)
    client = _client(seeded, llm)
    note = _create_note(client)

    resp = client.post(f"/api/v1/notes/{note['id']}/analyze")

    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["status"] == "completed"
    assert result["code_sets"] == {"icd10cm": "ICD10CM-FY2027", "cpt": None}
    assert [(s["code"], s["evidence"]) for s in result["suggestions"]] == [
        (e["code"], e["evidence"]) for e in WORKED["expected"]
    ]
    for s in result["suggestions"]:
        assert [r["rule_id"] for r in s["rule_results"]] == ["R1"]
        assert s["confidence"] == "review"
    assert result["model_errors"] == 0
    assert result["em"] is None

    # The select call only saw candidates retrieved from the code tables.
    select_payload = json.loads(dict(llm.calls)["select"])
    assert {f["fact_id"] for f in select_payload["facts"]} == {"f1", "f2"}

    with Session(seeded) as s:
        row = s.get(AnalysisRow, result["analysis_id"])
        assert row is not None
        assert row.status == "completed"
        assert row.result_json == result


def test_analyze_code_set_missing_is_409_and_not_stored(seeded: Engine) -> None:
    client = _client(seeded, ScriptedLlm(extract=EXTRACT, select=SELECT))
    note = _create_note(client, visit_date="2026-03-31")

    resp = client.post(f"/api/v1/notes/{note['id']}/analyze")

    assert (resp.status_code, resp.json()["error_code"]) == (409, "CODE_SET_MISSING")
    with Session(seeded) as s:
        rows = s.scalars(select(AnalysisRow).where(AnalysisRow.note_id == note["id"])).all()
        assert rows == []


@pytest.mark.parametrize(
    ("steps", "status", "code"),
    [
        ({"extract": LlmError("LLM_UNAVAILABLE", "down")}, 503, "LLM_UNAVAILABLE"),
        ({"extract": EXTRACT, "select": LlmError("LLM_BAD_OUTPUT", "bad")}, 503, "LLM_BAD_OUTPUT"),
    ],
)
def test_llm_failure_stores_failed_analysis_without_partial_results(
    seeded: Engine, steps: dict[str, Any], status: int, code: str
) -> None:
    client = _client(seeded, ScriptedLlm(**steps))
    note = _create_note(client)

    resp = client.post(f"/api/v1/notes/{note['id']}/analyze")

    body = resp.json()
    assert (resp.status_code, body["error_code"]) == (status, code)
    with Session(seeded) as s:
        row = s.get(AnalysisRow, body["analysis_id"])
        assert row is not None
        assert row.status == "failed"
        assert row.result_json["suggestions"] == []
        assert row.result_json["facts"] == []
        assert row.result_json["error"]["code"] == code


def test_unexpected_stage_error_is_pipeline_error(seeded: Engine) -> None:
    client = _client(seeded, ScriptedLlm(extract=EXTRACT, select=SELECT), BrokenEmbedder())
    note = _create_note(client)

    resp = client.post(f"/api/v1/notes/{note['id']}/analyze")

    assert (resp.status_code, resp.json()["error_code"]) == (500, "PIPELINE_ERROR")


def _note_and_sets(seeded: Engine) -> Any:
    client = _client(seeded, ScriptedLlm())
    note_id = _create_note(client)["id"]
    with Session(seeded) as s:
        note = repo.get_note(s, note_id)
        assert note is not None
        return note, resolve_code_sets(s, note.visit_date)


def test_timeout_when_deadline_passes(seeded: Engine) -> None:
    note, sets = _note_and_sets(seeded)
    ticks = iter([0.0, 0.0, 1000.0, 1000.0, 1000.0, 1000.0])
    with Session(seeded) as s:
        result = run_pipeline(
            PipelineDeps(s, ScriptedLlm(extract=EXTRACT, select=SELECT), FakeEmbedder()),
            note,
            sets,
            clock=lambda: next(ticks),
        )
    assert result.status == "failed"
    assert result.error is not None
    assert (result.error.code, result.error.stage) == ("TIMEOUT", "retrieve_candidates")


def test_model_errors_count_dropped_facts_and_selections(seeded: Engine) -> None:
    note, sets = _note_and_sets(seeded)
    extract = EXTRACT.model_copy(deep=True)
    extract.facts.append(extract.facts[0].model_copy(update={"fact_id": "f3", "evidence": [42]}))
    select_out = SELECT.model_copy(deep=True)
    select_out.selections.append(
        select_out.selections[0].model_copy(update={"code": "Z99.999"})  # not a candidate
    )
    with Session(seeded) as s:
        result = run_pipeline(
            PipelineDeps(s, ScriptedLlm(extract=extract, select=select_out), FakeEmbedder()),
            note,
            sets,
        )
    assert result.status == "completed"
    assert result.model_errors == 2
    assert [x.code for x in result.suggestions] == ["E11.22", "N18.30"]


def test_unconfigured_llm_is_503_and_code_set_check_still_wins(
    seeded: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    for var in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.setenv(var, "")
    get_settings.cache_clear()
    client = _client(seeded, ScriptedLlm())
    app.dependency_overrides.pop(get_llm)  # use the real client factory
    try:
        note = _create_note(client)
        resp = client.post(f"/api/v1/notes/{note['id']}/analyze")
        assert (resp.status_code, resp.json()["error_code"]) == (503, "LLM_UNAVAILABLE")

        old = _create_note(client, visit_date="2026-03-31")
        resp = client.post(f"/api/v1/notes/{old['id']}/analyze")
        assert (resp.status_code, resp.json()["error_code"]) == (409, "CODE_SET_MISSING")
    finally:
        get_settings.cache_clear()
