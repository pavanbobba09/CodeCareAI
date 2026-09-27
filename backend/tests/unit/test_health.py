from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db import repo
from app.db.session import get_session
from app.main import app


def _no_db_session() -> Iterator[None]:
    yield None


@pytest.fixture
def client() -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = _no_db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health_reports_db_and_code_sets(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(repo, "code_set_ids", lambda _s: ["ICD10CM-FY2027"])

    resp = client.get("/api/v1/health")

    assert resp.status_code == 200
    assert resp.json() == {"service": "codecare-api", "db": True, "code_sets": ["ICD10CM-FY2027"]}


def test_health_returns_db_error_when_db_down(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(_s: Session) -> list[str]:
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    monkeypatch.setattr(repo, "code_set_ids", boom)

    resp = client.get("/api/v1/health")

    assert resp.status_code == 500
    assert resp.json()["error_code"] == "DB_ERROR"
