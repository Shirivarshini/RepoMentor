import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationFailed
from app.main import create_app

SENSITIVE = "internal-detail password=hunter2"


@pytest.fixture
def app_with_test_routes(app: FastAPI) -> FastAPI:
    @app.get("/_test/validate")
    async def validate(limit: int) -> dict[str, int]:
        return {"limit": limit}

    @app.get("/_test/not-found")
    async def not_found() -> None:
        raise NotFoundError("Nothing here.")

    @app.get("/_test/invalid")
    async def invalid() -> None:
        raise ValidationFailed("Bad input.", field="question", reason="Too short.")

    @app.get("/_test/boom")
    async def boom() -> None:
        raise RuntimeError(SENSITIVE)

    return app


@pytest.fixture
def test_client(app_with_test_routes: FastAPI) -> TestClient:
    return TestClient(app_with_test_routes)


def assert_envelope(
    response_json: dict[str, object], code: str, request_id: str
) -> dict[str, object]:
    assert set(response_json) == {"error"}
    error = response_json["error"]
    assert isinstance(error, dict)
    assert set(error) == {"code", "message", "details", "request_id"}
    assert error["code"] == code
    assert error["request_id"] == request_id
    return error


def test_unknown_route_returns_not_found_envelope(client: TestClient) -> None:
    response = client.get("/nope")
    assert response.status_code == 404
    assert_envelope(response.json(), "NOT_FOUND", response.headers["x-request-id"])


def test_unknown_route_under_api_v1_returns_not_found_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert_envelope(response.json(), "NOT_FOUND", response.headers["x-request-id"])


def test_wrong_method_maps_to_not_found_envelope(client: TestClient) -> None:
    response = client.post("/health")
    assert response.status_code == 404
    assert_envelope(response.json(), "NOT_FOUND", response.headers["x-request-id"])


def test_request_validation_error_uses_envelope(test_client: TestClient) -> None:
    response = test_client.get("/_test/validate", params={"limit": "abc"})
    assert response.status_code == 422
    error = assert_envelope(response.json(), "VALIDATION_ERROR", response.headers["x-request-id"])
    assert error["details"]["field"] == "limit"  # type: ignore[index]
    assert "abc" not in response.text  # submitted input is never echoed


def test_app_errors_are_mapped_to_envelope(test_client: TestClient) -> None:
    response = test_client.get("/_test/not-found")
    assert response.status_code == 404
    error = assert_envelope(response.json(), "NOT_FOUND", response.headers["x-request-id"])
    assert error["message"] == "Nothing here."

    response = test_client.get("/_test/invalid")
    assert response.status_code == 422
    error = assert_envelope(response.json(), "VALIDATION_ERROR", response.headers["x-request-id"])
    assert error["details"] == {"field": "question", "reason": "Too short."}


def test_unhandled_exception_returns_generic_500_without_leaking(
    test_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    response = test_client.get("/_test/boom")
    assert response.status_code == 500
    error = assert_envelope(response.json(), "INTERNAL_ERROR", response.headers["x-request-id"])
    assert error["message"] == "An unexpected error occurred."
    for leaked in ("hunter2", "internal-detail", "RuntimeError", "Traceback"):
        assert leaked not in response.text


def test_500_responses_keep_cors_headers(test_client: TestClient) -> None:
    response = test_client.get("/_test/boom", headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_preflight_allows_configured_origin(client: TestClient) -> None:
    response = client.options(
        "/health",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_rejects_unknown_origin(client: TestClient) -> None:
    response = client.get("/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in response.headers


def test_docs_are_hidden_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    get_settings.cache_clear()
    with TestClient(create_app()) as production_client:
        assert production_client.get("/docs").status_code == 404
        assert production_client.get("/openapi.json").status_code == 404
        assert production_client.get("/health").status_code == 200
