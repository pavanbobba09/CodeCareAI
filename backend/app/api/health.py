from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import repo
from app.db.session import get_session
from app.errors import ApiError
from app.models import ErrorResponse, HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={500: {"model": ErrorResponse}},
)
def health(session: Annotated[Session, Depends(get_session)]) -> HealthResponse:
    try:
        code_sets = repo.code_set_ids(session)
    except SQLAlchemyError as exc:
        raise ApiError(500, "DB_ERROR", "Database is unreachable.") from exc
    return HealthResponse(service="codecare-api", db=True, code_sets=code_sets)
