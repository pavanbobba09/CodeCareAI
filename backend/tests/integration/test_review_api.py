"""M7: GET /analyses/{id}, reviews (accept, edit, reject), history and note versions."""

from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db import repo
from app.db.models import Code, CodeSet, ReviewRow
from app.llm.client import LlmError
from app.models import AnalysisResult
from tests.fakes import ScriptedLlm
from tests.integration.test_pipeline_api import EXTRACT, SELECT, _client, _create_note

API = "/api/v1"


def _analyzed(seeded: Engine) -> tuple[TestClient, dict[str, Any], dict[str, Any]]:
    """A note analyzed with the scripted worked example: s1 = E11.22, s2 = N18.30."""
    client = _client(seeded, ScriptedLlm(extract=EXTRACT, select=SELECT))
    note = _create_note(client)
    resp = client.post(f"{API}/notes/{note['id']}/analyze")
    assert resp.status_code == 200, resp.text
    analysis: dict[str, Any] = resp.json()
    assert [(s["suggestion_id"], s["code"]) for s in analysis["suggestions"]] == [
        ("s1", "E11.22"),
        ("s2", "N18.30"),
    ]
    return client, note, analysis


def _review(client: TestClient, analysis_id: str, sid: str, **body: Any) -> Any:
    return client.post(f"{API}/analyses/{analysis_id}/suggestions/{sid}/reviews", json=body)


def _error(resp: Any) -> tuple[int, str]:
    return resp.status_code, resp.json()["error_code"]


def _review_rows(seeded: Engine, analysis_id: str) -> int:
    with Session(seeded) as s:
        n = s.scalar(
            select(func.count()).select_from(ReviewRow).where(ReviewRow.analysis_id == analysis_id)
        )
    return int(n or 0)


# GET /analyses/{id}


def test_read_analysis_returns_the_stored_result(seeded: Engine) -> None:
    client, _, analysis = _analyzed(seeded)

    resp = client.get(f"{API}/analyses/{analysis['analysis_id']}")

    assert resp.status_code == 200
    assert resp.json() == analysis


def test_read_failed_analysis_and_unknown_analysis(seeded: Engine) -> None:
    client = _client(seeded, ScriptedLlm(extract=LlmError("LLM_UNAVAILABLE", "down")))
    note = _create_note(client)
    failed_id = client.post(f"{API}/notes/{note['id']}/analyze").json()["analysis_id"]

    failed = client.get(f"{API}/analyses/{failed_id}").json()
    assert (failed["status"], failed["suggestions"], failed["error"]["code"]) == (
        "failed",
        [],
        "LLM_UNAVAILABLE",
    )
    assert _error(client.get(f"{API}/analyses/nope")) == (404, "ANALYSIS_NOT_FOUND")


# POST reviews


def test_accept_edit_and_reject_are_stored_as_events(seeded: Engine) -> None:
    client, _, analysis = _analyzed(seeded)
    aid = analysis["analysis_id"]

    accept = _review(client, aid, "s1", action="accept")
    edit = _review(client, aid, "s2", action="edit", replacement_code="N18.31", reason="3a on labs")
    reject = _review(client, aid, "s2", action="reject", reason="not addressed at this visit")

    assert [r.status_code for r in (accept, edit, reject)] == [201, 201, 201]
    event = edit.json()
    assert {
        k: event[k] for k in ("analysis_id", "suggestion_id", "action", "replacement_code")
    } == {
        "analysis_id": aid,
        "suggestion_id": "s2",
        "action": "edit",
        "replacement_code": "N18.31",
    }
    assert event["id"] and event["created_at"]
    assert (accept.json()["replacement_code"], reject.json()["reason"]) == (
        None,
        "not addressed at this visit",
    )
    assert _review_rows(seeded, aid) == 3  # a second review of s2 is a new row


@pytest.mark.parametrize(
    "body",
    [
        {"action": "edit"},
        {"action": "edit", "replacement_code": ""},
        {"action": "reject"},
        {"action": "reject", "reason": "   "},
        {"action": "reject", "reason": "wrong", "replacement_code": "N18.31"},
        {"action": "accept", "replacement_code": "N18.31"},
        {"action": "accept", "reason": "fine"},
        {"action": "approve"},
    ],
)
def test_review_body_errors_are_validation_errors(seeded: Engine, body: dict[str, Any]) -> None:
    client, _, analysis = _analyzed(seeded)

    resp = _review(client, analysis["analysis_id"], "s1", **body)

    assert _error(resp) == (422, "VALIDATION_ERROR")
    assert _review_rows(seeded, analysis["analysis_id"]) == 0


def test_review_of_unknown_analysis_or_suggestion(seeded: Engine) -> None:
    client, _, analysis = _analyzed(seeded)

    assert _error(_review(client, "nope", "s1", action="accept")) == (404, "ANALYSIS_NOT_FOUND")
    assert _error(_review(client, analysis["analysis_id"], "s99", action="accept")) == (
        404,
        "SUGGESTION_NOT_FOUND",
    )


def test_failed_analysis_has_no_suggestions_to_review(seeded: Engine) -> None:
    client = _client(seeded, ScriptedLlm(extract=LlmError("LLM_UNAVAILABLE", "down")))
    note = _create_note(client)
    failed_id = client.post(f"{API}/notes/{note['id']}/analyze").json()["analysis_id"]

    assert _error(_review(client, failed_id, "s1", action="accept")) == (
        404,
        "SUGGESTION_NOT_FOUND",
    )


@pytest.fixture(scope="module")
def other_release(seeded: Engine) -> str:
    """A code that exists only in an older release, not in the analysis's FY2027 set."""
    with Session(seeded) as s, s.begin():
        if s.get(CodeSet, "ICD10CM-TEST-OLD") is None:
            s.add(
                CodeSet(
                    id="ICD10CM-TEST-OLD",
                    system="ICD-10-CM",
                    valid_from=date(2000, 10, 1),
                    valid_to=date(2001, 9, 30),
                    source_url=None,
                )
            )
            s.flush()
            s.add(
                Code(
                    code_set_id="ICD10CM-TEST-OLD",
                    code="Q99.98",
                    description="Synthetic code only in an old release",
                    billable=True,
                    parent_code=None,
                )
            )
    return "Q99.98"


@pytest.mark.parametrize(
    ("replacement", "message"),
    [
        ("Z99.999", "not in ICD10CM-FY2027"),
        ("N18.3", "not billable"),
        ("N18.30", "use accept"),
        ("OLD-RELEASE", "not in ICD10CM-FY2027"),
    ],
)
def test_edit_replacement_must_be_a_different_billable_code_in_the_visit_code_set(
    seeded: Engine, other_release: str, replacement: str, message: str
) -> None:
    client, _, analysis = _analyzed(seeded)
    code = other_release if replacement == "OLD-RELEASE" else replacement

    resp = _review(client, analysis["analysis_id"], "s2", action="edit", replacement_code=code)

    assert _error(resp) == (422, "INVALID_REPLACEMENT_CODE")
    assert message in resp.json()["message"]
    assert _review_rows(seeded, analysis["analysis_id"]) == 0


def test_not_suggested_codes_can_still_be_reviewed(seeded: Engine) -> None:
    """Owner decision N: the coder has the final say; the UI hides these codes (M8)."""
    client, _, analysis = _analyzed(seeded)
    stored = AnalysisResult.model_validate(analysis)
    hidden = stored.model_copy(
        update={
            "analysis_id": "a-not-suggested",
            "suggestions": [
                s.model_copy(update={"confidence": "not_suggested"}) for s in stored.suggestions
            ],
        }
    )
    with Session(seeded) as s:
        repo.insert_analysis(s, hidden)
        s.commit()

    for action in ({"action": "accept"}, {"action": "reject", "reason": "agree, uncertain"}):
        assert _review(client, "a-not-suggested", "s1", **action).status_code == 201


def test_review_db_failure_is_db_error_and_stores_nothing(
    seeded: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _, analysis = _analyzed(seeded)

    def broken(*_: Any, **__: Any) -> Any:
        raise OperationalError("INSERT INTO reviews", {}, Exception("db down"))

    monkeypatch.setattr(repo, "insert_review", broken)
    resp = _review(client, analysis["analysis_id"], "s1", action="accept")

    assert _error(resp) == (500, "DB_ERROR")
    assert _review_rows(seeded, analysis["analysis_id"]) == 0


# Analyze errors not covered elsewhere


def test_analyze_timeout_is_503_with_analysis_id(seeded: Engine) -> None:
    client = _client(seeded, ScriptedLlm(extract=LlmError("TIMEOUT", "slow")))
    note = _create_note(client)

    resp = client.post(f"{API}/notes/{note['id']}/analyze")

    assert _error(resp) == (503, "TIMEOUT")
    assert resp.json()["analysis_id"]


def test_analyze_db_failure_is_db_error(seeded: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(seeded, ScriptedLlm(extract=EXTRACT, select=SELECT))
    note = _create_note(client)

    def broken(*_: Any, **__: Any) -> Any:
        raise OperationalError("INSERT INTO analyses", {}, Exception("db down"))

    monkeypatch.setattr(repo, "insert_analysis", broken)
    resp = client.post(f"{API}/notes/{note['id']}/analyze")

    assert _error(resp) == (500, "DB_ERROR")


# History and versions


def test_history_lists_analyses_newest_first_and_reviews_oldest_first(seeded: Engine) -> None:
    client, note, first = _analyzed(seeded)
    second = client.post(f"{API}/notes/{note['id']}/analyze").json()
    _review(client, first["analysis_id"], "s1", action="accept")
    _review(client, second["analysis_id"], "s2", action="reject", reason="duplicate")
    _review(client, second["analysis_id"], "s2", action="accept")  # changed their mind

    history = client.get(f"{API}/notes/{note['id']}/history").json()

    assert history["note"] == note
    assert [a["analysis_id"] for a in history["analyses"]] == [
        second["analysis_id"],
        first["analysis_id"],
    ]
    assert [(r["analysis_id"], r["action"]) for r in history["reviews"]] == [
        (first["analysis_id"], "accept"),
        (second["analysis_id"], "reject"),
        (second["analysis_id"], "accept"),
    ]
    assert (history["previous_versions"], history["later_versions"]) == ([], [])


def test_history_of_unknown_note(seeded: Engine) -> None:
    client = _client(seeded, ScriptedLlm())

    assert _error(client.get(f"{API}/notes/nope/history")) == (404, "NOTE_NOT_FOUND")


def test_revised_note_starts_without_the_old_approvals(seeded: Engine) -> None:
    client, v1, analysis = _analyzed(seeded)
    _review(client, analysis["analysis_id"], "s1", action="accept")
    v2 = _create_note(client, parent_note_id=v1["id"])
    v3 = _create_note(client, parent_note_id=v2["id"])

    h1 = client.get(f"{API}/notes/{v1['id']}/history").json()
    h2 = client.get(f"{API}/notes/{v2['id']}/history").json()
    h3 = client.get(f"{API}/notes/{v3['id']}/history").json()

    assert (h1["previous_versions"], h1["later_versions"]) == ([], [v2["id"], v3["id"]])
    assert (h2["previous_versions"], h2["later_versions"]) == ([v1["id"]], [v3["id"]])
    assert (h3["previous_versions"], h3["later_versions"]) == ([v1["id"], v2["id"]], [])
    assert len(h1["reviews"]) == 1
    assert (h2["analyses"], h2["reviews"]) == ([], [])
