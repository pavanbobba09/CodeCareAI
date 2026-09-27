"""Integration tests run against a separate database so they never wipe dev data.

TEST_DATABASE_URL wins; otherwise DATABASE_URL's database name gets a `_test` suffix.
The schema is rebuilt from migrations once per session.
"""

import csv
import hashlib
import math
import os
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import EMBEDDING_DIM, Abbreviation, CodeSet
from app.db.session import get_engine
from app.loaders.icd10cm import Release, parse_sources, store_release
from app.terminology.embed_codes import embed_code_set

FIXTURES = Path(__file__).parent.parent / "fixtures" / "icd10cm"
ABBREVIATIONS_CSV = Path(__file__).parents[3] / "data" / "abbreviations.csv"

TEST_RELEASE = Release(
    fy=2027,
    valid_from=date(2026, 10, 1),
    valid_to=date(2027, 9, 30),
    order_zip="unused",
    tables_zip="unused",
)


def _use_test_database() -> None:
    base = make_url(get_settings().database_url)
    url = os.environ.get("TEST_DATABASE_URL") or base.set(
        database=f"{base.database}_test"
    ).render_as_string(hide_password=False)
    test_name = make_url(url).database
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": test_name})
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{test_name}"'))
    admin.dispose()
    os.environ["DATABASE_URL"] = url
    get_settings.cache_clear()
    get_engine.cache_clear()


class FakeEmbedder:
    """Deterministic bag-of-words hashing into 384 dims. No model download."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            vec = [0.0] * EMBEDDING_DIM
            for token in re.findall(r"[a-z0-9]+", t.lower()):
                vec[int(hashlib.md5(token.encode()).hexdigest(), 16) % EMBEDDING_DIM] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            out.append([v / norm for v in vec])
        return out


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    _use_test_database()
    cfg = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield get_engine()


@pytest.fixture(scope="session")
def seeded(engine: Engine) -> Engine:
    """FY2027 fixture codes + index + abbreviations + embeddings, and a CPT code set row."""

    parsed = parse_sources(
        (FIXTURES / "icd10cm_order_2027.txt").read_text(),
        ET.parse(FIXTURES / "icd10cm_tabular_2027.xml").getroot(),
        ET.parse(FIXTURES / "icd10cm_index_2027.xml").getroot(),
    )
    with Session(engine) as session, session.begin():
        store_release(session, TEST_RELEASE, parsed)
        session.merge(
            CodeSet(
                id="CPT-DEMO-2026",
                system="CPT",
                valid_from=date(2026, 1, 1),
                valid_to=None,
                source_url=None,
            )
        )
        # The real project mapping, so abbreviation fixes stay covered by tests.
        with ABBREVIATIONS_CSV.open(newline="") as f:
            for row in csv.DictReader(f):
                session.merge(Abbreviation(abbr=row["abbr"].upper(), expansion=row["expansion"]))
    with Session(engine) as session:
        embed_code_set(session, TEST_RELEASE.code_set_id, FakeEmbedder())
    return engine
