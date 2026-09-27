"""API errors. Codes come from DESIGN.md §4.4 and §6; add new ones there first."""

from typing import Literal

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.models import ErrorResponse

ErrorCode = Literal[
    "VALIDATION_ERROR",
    "NOTE_NOT_FOUND",
    "PARENT_NOTE_NOT_FOUND",
    "ANALYSIS_NOT_FOUND",
    "INVALID_REPLACEMENT_CODE",
    "CODE_SET_MISSING",
    "LLM_UNAVAILABLE",
    "LLM_BAD_OUTPUT",
    "TIMEOUT",
    "DB_ERROR",
]


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        error_code: ErrorCode,
        message: str,
        analysis_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = ErrorResponse(error_code=error_code, message=message, analysis_id=analysis_id)


async def _handle_api_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApiError)
    return JSONResponse(status_code=exc.status_code, content=exc.body.model_dump())


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _handle_api_error)
