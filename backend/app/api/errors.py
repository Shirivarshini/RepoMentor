"""Exception handlers that produce the standard error envelope (API_CONTRACT.md)."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppError
from app.core.logging import get_request_id
from app.schemas.errors import ErrorBody, ErrorCode, ErrorResponse

_NON_FIELD_LOCATIONS = {"body", "query", "path", "header", "cookie"}


def error_response(
    status_code: int,
    code: ErrorCode,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorBody(
            code=code,
            message=message,
            details=details or {},
            request_id=get_request_id() or "unavailable",
        )
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
    response = error_response(exc.status_code, exc.code, exc.message, exc.details)
    if "retry_after_seconds" in exc.details:
        response.headers["Retry-After"] = str(exc.details["retry_after_seconds"])
    return response


async def _handle_database_error(_: Request, exc: SQLAlchemyError) -> JSONResponse:
    return error_response(
        503, ErrorCode.DATABASE_ERROR, "Database unavailable. Please retry later."
    )


async def _handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Report the first problem only; never echo the submitted input.
    first = exc.errors()[0]
    field = ".".join(str(part) for part in first["loc"] if part not in _NON_FIELD_LOCATIONS)
    return error_response(
        422,
        ErrorCode.VALIDATION_ERROR,
        "The request is invalid.",
        {"field": field or None, "reason": first["msg"]},
    )


async def _handle_http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    # The contract has no method-not-allowed code, so 404 and 405 both map to NOT_FOUND.
    if exc.status_code in (404, 405):
        return error_response(404, ErrorCode.NOT_FOUND, "Resource not found.")
    if exc.status_code >= 500:
        return error_response(500, ErrorCode.INTERNAL_ERROR, "An unexpected error occurred.")
    return error_response(
        exc.status_code, ErrorCode.VALIDATION_ERROR, "The request could not be processed."
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Unhandled exceptions are handled in RequestContextMiddleware (see middleware.py)."""
    app.add_exception_handler(AppError, _handle_app_error)  # type: ignore[arg-type]
    app.add_exception_handler(SQLAlchemyError, _handle_database_error)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _handle_validation_error)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)  # type: ignore[arg-type]
