import re

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_every_response_has_a_request_id(client: TestClient) -> None:
    request_id = client.get("/health").headers["x-request-id"]
    assert re.fullmatch(r"[0-9a-f]{16}", request_id)


def test_well_formed_inbound_request_id_is_echoed(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "trace-1234-abcd"})
    assert response.headers["x-request-id"] == "trace-1234-abcd"


def test_malformed_inbound_request_id_is_replaced(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "bad id\twith spaces"})
    assert re.fullmatch(r"[0-9a-f]{16}", response.headers["x-request-id"])


def test_docs_are_available_in_development(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
