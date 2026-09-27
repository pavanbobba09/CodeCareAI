"""Analyses and reviews (DESIGN.md §4.2, §6). Reviews are append-only."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import repo
from app.db.session import get_session
from app.errors import ApiError
from app.models import AnalysisResult, ErrorResponse, ReviewEvent, ReviewRequest, Suggestion
from app.terminology.lookup import DbCodeLookup

log = logging.getLogger(__name__)
router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]


def _analysis(session: Session, analysis_id: str) -> AnalysisResult:
    analysis = repo.get_analysis(session, analysis_id)
    if analysis is None:
        raise ApiError(404, "ANALYSIS_NOT_FOUND", "Analysis not found.")
    return analysis


@router.get(
    "/analyses/{analysis_id}",
    response_model=AnalysisResult,
    responses={404: {"model": ErrorResponse}},
)
def read_analysis(analysis_id: str, session: SessionDep) -> AnalysisResult:
    return _analysis(session, analysis_id)


def _check_replacement(
    session: Session, analysis: AnalysisResult, suggestion: Suggestion, code: str
) -> None:
    """An edit must name a different code that exists and is billable in the analysis's own
    code set for the suggestion's system (the release valid on the visit date)."""
    if code == suggestion.code:
        raise ApiError(
            422,
            "INVALID_REPLACEMENT_CODE",
            f"{code} is the suggested code; use accept instead of edit.",
        )
    sets = analysis.code_sets
    code_set_id = sets.cpt if suggestion.system == "CPT" else sets.icd10cm
    lookup = DbCodeLookup(session)
    if code_set_id is None or lookup.get_code(code, code_set_id) is None:
        raise ApiError(
            422, "INVALID_REPLACEMENT_CODE", f"{code} is not in {code_set_id or 'any code set'}."
        )
    if not lookup.is_billable(code, code_set_id):
        raise ApiError(422, "INVALID_REPLACEMENT_CODE", f"{code} is not billable.")


@router.post(
    "/analyses/{analysis_id}/suggestions/{suggestion_id}/reviews",
    status_code=201,
    response_model=ReviewEvent,
    responses={
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def review_suggestion(
    analysis_id: str, suggestion_id: str, body: ReviewRequest, session: SessionDep
) -> ReviewEvent:
    analysis = _analysis(session, analysis_id)
    suggestion = next((s for s in analysis.suggestions if s.suggestion_id == suggestion_id), None)
    if suggestion is None:
        raise ApiError(404, "SUGGESTION_NOT_FOUND", "Suggestion not found in this analysis.")
    if body.action == "edit":
        assert body.replacement_code is not None  # ReviewRequest validates this
        _check_replacement(session, analysis, suggestion, body.replacement_code)
    try:
        event = repo.insert_review(session, analysis_id, suggestion_id, body)
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        log.exception("could not store review for %s/%s", analysis_id, suggestion_id)
        raise ApiError(500, "DB_ERROR", "Could not store the review.") from exc
    return event
