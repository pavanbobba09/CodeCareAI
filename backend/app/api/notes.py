import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_embedder, get_llm
from app.db import repo
from app.db.session import get_session
from app.errors import ApiError
from app.llm.client import JsonLlm
from app.models import AnalysisResult, ErrorResponse, Note, NoteCreate, NoteHistory
from app.pipeline.graph import run_pipeline
from app.pipeline.state import PipelineDeps
from app.segment.segmenter import segment_note
from app.terminology.code_sets import CodeSetMissingError, resolve_code_sets
from app.terminology.embedder import Embedder

log = logging.getLogger(__name__)
router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]

# Pipeline error code -> HTTP status (DESIGN.md §6).
PIPELINE_STATUS = {
    "LLM_UNAVAILABLE": 503,
    "LLM_BAD_OUTPUT": 503,
    "TIMEOUT": 503,
    "PIPELINE_ERROR": 500,
}


@router.post(
    "/notes",
    status_code=201,
    response_model=Note,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def create_note(body: NoteCreate, session: SessionDep) -> Note:
    if body.parent_note_id is not None and not repo.note_exists(session, body.parent_note_id):
        raise ApiError(404, "PARENT_NOTE_NOT_FOUND", "Parent note not found.")
    try:
        note = repo.insert_note(session, body, segment_note(body.text))
        session.commit()
    except SQLAlchemyError as exc:
        raise ApiError(500, "DB_ERROR", "Could not store the note.") from exc
    return note


@router.get("/notes/{note_id}", response_model=Note, responses={404: {"model": ErrorResponse}})
def read_note(note_id: str, session: SessionDep) -> Note:
    note = repo.get_note(session, note_id)
    if note is None:
        raise ApiError(404, "NOTE_NOT_FOUND", "Note not found.")
    return note


@router.get(
    "/notes/{note_id}/history",
    response_model=NoteHistory,
    responses={404: {"model": ErrorResponse}},
)
def note_history(note_id: str, session: SessionDep) -> NoteHistory:
    """One note version: its analyses and their reviews. A revised note is a new note, so
    reviews of an earlier version never carry forward (DESIGN.md §4.2)."""
    note = repo.get_note(session, note_id)
    if note is None:
        raise ApiError(404, "NOTE_NOT_FOUND", "Note not found.")
    analyses = repo.list_analyses(session, note_id)
    return NoteHistory(
        note=note,
        previous_versions=repo.previous_versions(session, note),
        later_versions=repo.later_versions(session, note_id),
        analyses=analyses,
        reviews=repo.list_reviews(session, [a.analysis_id for a in analyses]),
    )


@router.post(
    "/notes/{note_id}/analyze",
    response_model=AnalysisResult,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def analyze_note(
    note_id: str,
    session: SessionDep,
    llm: Annotated[JsonLlm, Depends(get_llm)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
) -> AnalysisResult:
    note = repo.get_note(session, note_id)
    if note is None:
        raise ApiError(404, "NOTE_NOT_FOUND", "Note not found.")
    try:
        code_sets = resolve_code_sets(session, note.visit_date)
    except CodeSetMissingError as exc:
        raise ApiError(409, "CODE_SET_MISSING", str(exc)) from exc

    result = run_pipeline(
        PipelineDeps(session=session, llm=llm, embedder=embedder), note, code_sets
    )
    session.rollback()  # end the read transaction used by the pipeline before writing
    try:
        repo.insert_analysis(session, result)
        session.commit()
    except SQLAlchemyError as exc:
        log.exception("could not store analysis %s", result.analysis_id)
        raise ApiError(500, "DB_ERROR", "Could not store the analysis.") from exc

    if result.error is not None:
        raise ApiError(
            PIPELINE_STATUS.get(result.error.code, 500),
            result.error.code,
            result.error.message,
            analysis_id=result.analysis_id,
        )
    return result
