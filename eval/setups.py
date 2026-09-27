"""The two systems under test, run on the same model: full pipeline and LLM-only baseline."""

import json
import re
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import IndexTerm
from app.llm.client import JsonLlm, LlmError
from app.llm.prompts import load_prompt
from app.models import AnalysisResult, ClinicalFact, Note
from app.models.eval import BaselineOutput, GoldNote
from app.pipeline.graph import rerun_rules, run_pipeline_state
from app.pipeline.state import (
    ANALYSIS_TIME_LIMIT_S,
    EXTRACT_PROMPT,
    PipelineDeps,
    SavedLlmOutputs,
    prompt_version,
)
from app.segment.segmenter import segment_note
from app.terminology.abbreviations import load_abbreviations
from app.terminology.code_sets import resolve_code_sets
from app.terminology.embedder import Embedder
from app.terminology.lookup import DbCodeLookup
from eval.records import NoteRun, PredictedCode
from eval.support import SupportContext, check_support

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
    session: Session,
    code_set_id: str,
    codes: list[tuple[str, list[int], list[str] | None]],
    sentences: dict[int, str],
) -> list[PredictedCode]:
    """Score-ready predictions: code-set validity plus the rule-based support check.

    Each item is (code, evidence, statuses of the code's facts); statuses are None when the
    setup has no facts (the LLM-only baseline).
    """
    lookup = DbCodeLookup(session)
    abbreviations = load_abbreviations(session)
    merged: dict[str, tuple[list[int], list[str] | None]] = {}
    for code, evidence, statuses in codes:
        prior_ev, prior_st = merged.get(code, ([], None))
        all_st = (
            None
            if statuses is None and prior_st is None
            else [*(prior_st or []), *(statuses or [])]
        )
        merged[code] = (sorted({*evidence, *prior_ev}), all_st)
    out = []
    for code, (evidence, statuses) in merged.items():
        found = lookup.get_code(code, code_set_id)
        ctx = SupportContext(
            description=found.description if found else "",
            index_paths=list(
                session.scalars(
                    select(IndexTerm.path).where(
                        IndexTerm.code_set_id == code_set_id, IndexTerm.code == code
                    )
                )
            ),
            abbreviations=abbreviations,
        )
        cited = [sentences[n] for n in evidence if n in sentences]
        supported, reason = check_support(code, cited, ctx, statuses)
        out.append(
            PredictedCode(
                code=code,
                evidence=evidence,
                in_code_set=found is not None,
                billable=found is not None and lookup.is_billable(code, code_set_id),
                supported=supported,
                support_reason=reason,
            )
        )
    return out


def _pipeline_run(
    session: Session,
    gold: GoldNote,
    note: Note,
    facts: list[ClinicalFact],
    code_set_id: str,
    result: AnalysisResult,
    model: str,
    version: str,
    llm_outputs: SavedLlmOutputs | None,
) -> NoteRun:
    # "not_suggested" codes are shown to the coder with the reason, not reported.
    reported = [s for s in result.suggestions if s.confidence != "not_suggested"]
    by_id = {f.fact_id: f for f in facts}
    return NoteRun(
        note_id=gold.note_id,
        setup="pipeline",
        model=model,
        prompt_version=version,
        status=result.status,
        error=result.error.code if result.error else None,
        attempts=1,
        n_sentences=len(note.sentences),
        predicted=_predicted(
            session,
            code_set_id,
            [
                (s.code, s.evidence, [by_id[f].status for f in s.fact_ids if f in by_id])
                for s in reported
            ],
            {x.n: x.text for x in note.sentences},
        ),
        gap_rules=sorted({g.rule_id for g in result.gaps if g.rule_id}),
        em_code=result.em.code if result.em else None,
        model_errors=result.model_errors,
        latency_ms=result.latency_ms,
        llm_outputs=llm_outputs,
    )


def predict_pipeline(
    session: Session,
    llm: JsonLlm,
    embedder: Embedder,
    gold: GoldNote,
    extract_prompt: str = EXTRACT_PROMPT,
) -> NoteRun:
    note = _note(gold)
    with session.begin():
        sets = resolve_code_sets(session, note.visit_date)
        state = run_pipeline_state(PipelineDeps(session, llm, embedder, extract_prompt), note, sets)
        assert state.result is not None
        saved = (
            SavedLlmOutputs(
                facts=state.facts,
                candidate_sets=state.candidate_sets,
                selections=state.selections,
                model_errors=state.model_errors - state.rule_model_errors,
            )
            if state.result.status == "completed"
            else None
        )
        return _pipeline_run(
            session,
            gold,
            note,
            state.facts,
            sets.icd10cm,
            state.result,
            llm.model,
            prompt_version(extract_prompt),
            saved,
        )


class _NoLlm:
    """Replay must never reach the LLM or the embedder."""

    def __init__(self, model: str) -> None:
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    def complete_json(
        self, step: str, system: str, user: str, schema: type[BaseModel], deadline: float
    ) -> Any:
        raise AssertionError("replay made an LLM call")

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise AssertionError("replay made an embedding call")


def predict_replay(session: Session, source: NoteRun, gold: GoldNote) -> NoteRun:
    """Rerun only the rules and assemble on a saved note's LLM outputs (no LLM calls)."""
    if source.status != "completed" or source.llm_outputs is None:
        error = source.error if source.status != "completed" else "NO_SAVED_OUTPUTS"
        return source.model_copy(
            update={
                "status": "failed",
                "error": error,
                "predicted": [],
                "gap_rules": [],
                "usage": [],
                "llm_outputs": None,
            }
        )
    note = _note(gold)
    stub = _NoLlm(source.model)
    extract_prompt = source.prompt_version.split("+")[0]
    with session.begin():
        sets = resolve_code_sets(session, note.visit_date)
        result = rerun_rules(
            PipelineDeps(session, stub, stub, extract_prompt), note, sets, source.llm_outputs
        )
        return _pipeline_run(
            session,
            gold,
            note,
            source.llm_outputs.facts,
            sets.icd10cm,
            result,
            source.model,
            source.prompt_version,
            source.llm_outputs,
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
            session,
            sets.icd10cm,
            [(normalize_code(c.code), c.evidence, None) for c in out.codes],
            {x.n: x.text for x in note.sentences},
        )
    return NoteRun(
        **base,
        status="completed",
        error=None,
        predicted=predicted,
        latency_ms=int((time.monotonic() - start) * 1000),
    )
