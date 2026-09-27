import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError

from app.main import app

pytestmark = pytest.mark.integration


def test_health_with_real_db(engine: Engine) -> None:
    resp = TestClient(app).get("/api/v1/health")

    assert resp.status_code == 200
    assert resp.json()["db"] is True


def test_all_design_tables_exist(engine: Engine) -> None:
    expected = {
        "code_sets",
        "codes",
        "index_terms",
        "abbreviations",
        "ncci_ptp",
        "notes",
        "analyses",
        "reviews",
    }
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        ).scalars()
        assert expected <= set(rows)


def test_reviews_are_append_only(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO notes (id, visit_date, patient_type, text, sentences) "
                "VALUES ('n-test', '2026-10-01', 'new', 'Synthetic test note.', '[]')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO analyses (id, note_id, status, result_json, model, prompt_version) "
                "VALUES ('a-test', 'n-test', 'completed', '{}', 'fake-model', 'v1')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO reviews (id, analysis_id, suggestion_id, action) "
                "VALUES ('r-test', 'a-test', 's1', 'accept')"
            )
        )

    for stmt in (
        "UPDATE reviews SET action = 'reject' WHERE id = 'r-test'",
        "DELETE FROM reviews WHERE id = 'r-test'",
        "TRUNCATE reviews",
    ):
        with pytest.raises(DBAPIError, match="append-only"), engine.begin() as conn:
            conn.execute(text(stmt))
