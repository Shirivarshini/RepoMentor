"""Standard error envelope. Mirrors the "Standard Error" section of API_CONTRACT.md."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ErrorCode(StrEnum):
    """Error codes defined by API_CONTRACT.md."""

    VALIDATION_ERROR = "VALIDATION_ERROR"
    REPOSITORY_NOT_FOUND = "REPOSITORY_NOT_FOUND"
    NOT_FOUND = "NOT_FOUND"
    ANALYSIS_NOT_READY = "ANALYSIS_NOT_READY"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    GITHUB_RATE_LIMIT = "GITHUB_RATE_LIMIT"
    GITHUB_API_ERROR = "GITHUB_API_ERROR"
    AI_PROVIDER_ERROR = "AI_PROVIDER_ERROR"
    EMBEDDING_ERROR = "EMBEDDING_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    # Asynchronous analysis failures: appear in status.error, never as an HTTP error.
    ANALYSIS_FAILED = "ANALYSIS_FAILED"
    REPOSITORY_TOO_LARGE = "REPOSITORY_TOO_LARGE"
    EMPTY_REPOSITORY = "EMPTY_REPOSITORY"
    UNSUPPORTED_REPOSITORY = "UNSUPPORTED_REPOSITORY"


class ErrorBody(BaseModel):
    code: ErrorCode
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorBody
