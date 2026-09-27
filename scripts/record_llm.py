"""Run the worked example against the real LLM and record responses for replay tests.

Needs LLM_BASE_URL, LLM_API_KEY, LLM_MODEL (backend/.env) and the loaded FY2027 tables.
Usage: python scripts/record_llm.py
Writes backend/tests/fixtures/llm/worked_example/{extract,select}.json only when the run passes.
"""

import json
import sys
import uuid
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from _common import DATA, REPO
from app.config import get_settings
from app.db.session import get_engine
from app.llm.client import LlmClient
from app.llm.replay import RecordingLlm
from app.models import Note
from app.pipeline.graph import run_pipeline
from app.pipeline.state import PipelineDeps
from app.segment.segmenter import segment_note
from app.terminology.code_sets import resolve_code_sets
from app.terminology.embedder import get_embedder

sys.path.insert(0, str(REPO))
from eval.budget import UsageLedger

OUT = REPO / "backend" / "tests" / "fixtures" / "llm" / "worked_example"


def main() -> None:
    example = json.loads((DATA / "examples" / "worked_example.json").read_text())
    body = example["note"]
    note = Note(
        id=str(uuid.uuid4()),
        visit_date=date.fromisoformat(body["visit_date"]),
        patient_type=body["patient_type"],
        text=body["text"],
        sentences=segment_note(body["text"]),
        parent_note_id=None,
        created_at=datetime.now(UTC),
    )
    s = get_settings()
    ledger = UsageLedger(s.llm_model)  # counts toward the eval token budget
    llm = RecordingLlm(
        LlmClient(s.llm_base_url, s.llm_api_key, s.llm_model, on_usage=ledger.record), OUT
    )
    with Session(get_engine()) as session, session.begin():
        sets = resolve_code_sets(session, note.visit_date)
        result = run_pipeline(PipelineDeps(session, llm, get_embedder()), note, sets)

    print(f"model={result.model} status={result.status} model_errors={result.model_errors}")
    if result.error:
        print(f"error: {result.error.code} at {result.error.stage}: {result.error.message}")
    for f in result.facts:
        print(f"fact {f.fact_id} {f.status} {f.concept!r} {f.details} evidence={f.evidence}")
    got = [(s.code, s.evidence) for s in result.suggestions]
    want = [(e["code"], e["evidence"]) for e in example["expected"]]
    print(f"suggestions: {got}")
    print(f"expected:    {want}")
    ok = result.status == "completed" and sorted(got) == sorted(want)
    print("PASS" if ok else "FAIL")
    if ok:
        for path in llm.save():
            print(f"recorded {path.relative_to(REPO)}")
    else:
        print("not recorded: existing fixtures left unchanged")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
