import json
import logging
import sys

import pytest

from app.core.logging import (
    REDACTED,
    JsonFormatter,
    RedactionFilter,
    redact,
    redact_value,
    request_id_var,
)


@pytest.mark.parametrize(
    ("raw", "secret"),
    [
        ("Authorization: Bearer abcdef1234567890", "abcdef1234567890"),
        ("GEMINI_API_KEY=AIzaSyA1234567890abcdefghijklmnopqrstuv", "AIzaSyA1234567890"),
        ('{"password": "hunter2"}', "hunter2"),
        ("connect postgresql+asyncpg://user:s3cr3tpw@db:5432/app", "s3cr3tpw"),
        ("token ghp_abcdefghijklmnopqrstuvwxyz0123456789", "ghp_abcdefghij"),
        ("using sk-abcdefghijklmnopqrstuvwxyz123456", "sk-abcdefghij"),
    ],
)
def test_redact_removes_secrets(raw: str, secret: str) -> None:
    result = redact(raw)
    assert secret not in result
    assert REDACTED in result


def test_redact_leaves_ordinary_text_alone() -> None:
    text = "analysis completed for owner/repository in 120 ms"
    assert redact(text) == text


def test_redact_value_by_key_name() -> None:
    assert redact_value("github_token", "anything") == REDACTED
    assert redact_value("headers", {"Authorization": "x", "accept": "json"}) == {
        "Authorization": REDACTED,
        "accept": "json",
    }


def _record(message: str, **extra: object) -> logging.LogRecord:
    record = logging.LogRecord("test", logging.INFO, __file__, 1, message, (), None)
    record.__dict__.update(extra)
    return record


def test_filter_and_formatter_produce_redacted_json() -> None:
    record = _record("login with password=hunter2", api_key="abc", route="/health")
    assert RedactionFilter().filter(record)
    payload = json.loads(JsonFormatter().format(record))
    assert "hunter2" not in payload["message"]
    assert payload["api_key"] == REDACTED
    assert payload["route"] == "/health"
    assert payload["level"] == "INFO"


def test_formatter_includes_request_id_when_set() -> None:
    token = request_id_var.set("abc123def4567890")
    try:
        payload = json.loads(JsonFormatter().format(_record("hello")))
    finally:
        request_id_var.reset(token)
    assert payload["request_id"] == "abc123def4567890"


def test_formatter_redacts_exception_text() -> None:
    try:
        raise RuntimeError("failed with password=hunter2")
    except RuntimeError:
        record = _record("boom")
        record.exc_info = sys.exc_info()
    payload = json.loads(JsonFormatter().format(record))
    assert "hunter2" not in payload["exception"]
    assert "RuntimeError" in payload["exception"]


def test_configure_logging_silences_uvicorn_access_log() -> None:
    from app.core.logging import configure_logging

    configure_logging("INFO")
    assert logging.getLogger("uvicorn.access").propagate is False
    assert logging.getLogger("uvicorn.error").propagate is True


def test_formatter_drops_uvicorn_color_message() -> None:
    payload = json.loads(JsonFormatter().format(_record("started", color_message="\x1b[36mx")))
    assert "color_message" not in payload
