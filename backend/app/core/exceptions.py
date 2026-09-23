"""Domain exceptions. Services raise these; the API layer maps them to the error envelope."""

from typing import Any

from app.schemas.errors import ErrorCode

# HTTP status for every code that can be returned synchronously (API_CONTRACT.md, Error Codes).
HTTP_STATUS_BY_CODE: dict[ErrorCode, int] = {
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.REPOSITORY_NOT_FOUND: 404,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.ANALYSIS_NOT_READY: 409,
    ErrorCode.RATE_LIMIT_EXCEEDED: 429,
    ErrorCode.GITHUB_RATE_LIMIT: 503,
    ErrorCode.GITHUB_API_ERROR: 502,
    ErrorCode.AI_PROVIDER_ERROR: 503,
    ErrorCode.EMBEDDING_ERROR: 503,
    ErrorCode.DATABASE_ERROR: 503,
    ErrorCode.INTERNAL_ERROR: 500,
}


class AppError(Exception):
    """Base class for errors that are returned to clients as the standard error envelope.

    `message` and `details` are sent to clients: never put secrets or internals in them.
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        # Asynchronous-only codes have no HTTP mapping; they fall back to 500 if raised.
        self.status_code = status_code or HTTP_STATUS_BY_CODE.get(code, 500)
        self.details = details or {}


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found.") -> None:
        super().__init__(ErrorCode.NOT_FOUND, message)


class ValidationFailed(AppError):
    def __init__(
        self, message: str, *, field: str | None = None, reason: str | None = None
    ) -> None:
        details: dict[str, Any] = {}
        if field is not None:
            details["field"] = field
        if reason is not None:
            details["reason"] = reason
        super().__init__(ErrorCode.VALIDATION_ERROR, message, details=details)
