"""The two systems under test, run on the same model: full pipeline and LLM-only baseline."""

import json
import re
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.llm.client import JsonLlm, LlmError
from app.llm.prompts import load_prompt
from app.models import Note
from app.models.eval import BaselineOutput, GoldNote
from app.pipeline.graph import run_pipeline
from app.pipeline.state import ANALYSIS_TIME_LIMIT_S, PROMPT_VERSION, PipelineDeps
from app.segment.segmenter import segment_note
from app.terminology.code_sets import resolve_code_sets
from app.terminology.embedder import Embedder
from app.terminology.lookup import DbCodeLookup
from eval.records import NoteRun, PredictedCode

BASELINE_PROMPT_VERSION = "baseline_v1"
_UNDOTTED = re.compile(r"^[A-Z]\d{2}[0-9A-Z]+$")


def normalize_code(code: str) -> str:
    """Upper-case and add the dot if the model left it out (E1122 -> E11.22)."""
    c = code.strip().upper()
    return f"{c[:3]}.{c[3:]}" if _UNDOTTED.match(c) else c


def _note(gold: GoldNote) -> Note:
    return Note(
        id=str(uuid.uuid4()),
        visit_date=gold.visit_date,
        patient_type=gold.patient_type,
        text=gold.text,
        sentences=segment_note(gold.text),
        parent_note_id=None,
        created_at=datetime.now(UTC),
    )


def _predicted(
    session: Session, code_set_id: str, codes: list[tuple[str, list[int]]]
) -> list[PredictedCode]:
    lookup = DbCodeLookup(session)
    out: dict[str, PredictedCode] = {}
    for code, evidence in codes:
        found = lookup.get_code(code, code_set_id)
        prior = out.get(code)
        merged = sorted({*evidence, *(prior.evidence if prior else [])})
        out[code] = PredictedCode(
            code=code,
            evidence=merged,
            in_code_set=found is not None,
            billable=found is not None and lookup.is_billable(code, code_set_id),
        )
    return list(out.values())


def predict_pipeline(session: Session, llm: JsonLlm, embedder: Embedder, gold: GoldNote) -> NoteRun:
    note = _note(gold)
    with session.begin():
        sets = resolve_code_sets(session, note.visit_date)
        result = run_pipeline(PipelineDeps(session, llm, embedder), note, sets)
        predicted = _predicted(
            session, sets.icd10cm, [(s.code, s.evidence) for s in result.suggestions]
        )
    return NoteRun(
        note_id=gold.note_id,
        setup="pipeline",
        model=llm.model,
        prompt_version=PROMPT_VERSION,
        status=result.status,
        error=result.error.code if result.error else None,
        attempts=1,
        n_sentences=len(note.sentences),
        predicted=predicted,
        gap_rules=sorted({g.rule_id for g in result.gaps if g.rule_id}),
        em_code=result.em.code if result.em else None,
        model_errors=result.model_errors,
        latency_ms=result.latency_ms,
    )


def predict_baseline(session: Session, llm: JsonLlm, gold: GoldNote) -> NoteRun:
    note = _note(gold)
    system = load_prompt(BASELINE_PROMPT_VERSION, BaselineOutput)
    user = json.dumps(
        {
            "patient_type": note.patient_type,
            "sentences": [{"n": s.n, "section": s.section, "text": s.text} for s in note.sentences],
        }
    )
    start = time.monotonic()
    base = {
        "note_id": gold.note_id,
        "setup": "baseline",
        "model": llm.model,
        "prompt_version": BASELINE_PROMPT_VERSION,
        "attempts": 1,
        "n_sentences": len(note.sentences),
        "gap_rules": [],  # the baseline has no gap logic
        "em_code": None,
        "model_errors": 0,
    }
    try:
        out = llm.complete_json(
            "baseline", system, user, BaselineOutput, start + ANALYSIS_TIME_LIMIT_S
        )
    except LlmError as exc:
        return NoteRun(
            **base,
            status="failed",
            error=exc.code,
            predicted=[],
            latency_ms=int((time.monotonic() - start) * 1000),
        )
    with session.begin():
        sets = resolve_code_sets(session, note.visit_date)
        predicted = _predicted(
            session, sets.icd10cm, [(normalize_code(c.code), c.evidence) for c in out.codes]
        )
    return NoteRun(
        **base,
        status="completed",
        error=None,
        predicted=predicted,
        latency_ms=int((time.monotonic() - start) * 1000),
    )
