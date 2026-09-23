"""Structured JSON logging with secret redaction and per-request correlation ids."""

import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

REDACTED = "[REDACTED]"

# Set by the request middleware; attached to every log line emitted while handling a request.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    return request_id_var.get()


_SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "private_key",
)

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Authorization headers, with or without a scheme.
    (
        re.compile(
            r"(?i)\b(authorization[\"']?\s*[:=]\s*)(?:(?:bearer|basic|token)\s+)?[^\s,;\"']+"
        ),
        rf"\1{REDACTED}",
    ),
    (re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/=-]{8,}"), rf"\1{REDACTED}"),
    # key=value / "key": "value" pairs whose key looks like a credential.
    (
        re.compile(
            r"(?i)\b([\w-]*(?:api[_-]?key|token|secret|passw(?:or)?d)[\w-]*[\"']?\s*[=:]\s*)"
            r"(?:\"[^\"]*\"|'[^']*'|[^\s,;&]+)"
        ),
        rf"\1{REDACTED}",
    ),
    # Credentials embedded in URLs: scheme://user:password@host
    (re.compile(r"(?i)(\b[a-z][a-z0-9+.-]*://[^/\s:@]+:)[^@\s/]+(@)"), rf"\1{REDACTED}\2"),
    # Well-known token formats.
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), REDACTED),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), REDACTED),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"), REDACTED),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), REDACTED),
]


def redact(text: str) -> str:
    """Remove credential-looking substrings from free text."""
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact_value(key: str, value: Any, _depth: int = 0) -> Any:
    """Redact a structured log field, by key name and by content."""
    if any(part in key.lower() for part in _SENSITIVE_KEY_PARTS):
        return REDACTED
    if isinstance(value, str):
        return redact(value)
    if _depth < 4 and isinstance(value, dict):
        return {str(k): redact_value(str(k), v, _depth + 1) for k, v in value.items()}
    if _depth < 4 and isinstance(value, (list, tuple)):
        return [redact_value(key, item, _depth + 1) for item in value]
    return value


# Fields uvicorn attaches to its records that only add noise (ANSI colour codes).
_SKIPPED_EXTRA_KEYS = frozenset({"color_message"})

# Attributes present on every LogRecord; anything else was supplied through `extra=`.
_STANDARD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


class RedactionFilter(logging.Filter):
    """Redacts the message and any `extra` fields of every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = None
        for key in list(record.__dict__):
            if key not in _STANDARD_ATTRS:
                record.__dict__[key] = redact_value(key, record.__dict__[key])
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = get_request_id()
        if request_id is not None:
            payload["request_id"] = request_id
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and key not in _SKIPPED_EXTRA_KEYS:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    """Route all logging (including uvicorn's) through one redacting JSON handler."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactionFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True

    # RequestContextMiddleware writes the one access-log line per request, so uvicorn's own
    # access log is silenced (this also keeps Docker health checks out of the logs).
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.handlers.clear()
    access_logger.propagate = False
