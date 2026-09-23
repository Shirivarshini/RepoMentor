from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.api.v1.repositories import ready_service
from app.github.client import GitHubClient


@pytest.fixture
def repository_client(client, app):
    app.dependency_overrides[ready_service] = lambda: None
    app.state.store = SimpleNamespace(get=AsyncMock(return_value=None))
    return client


def test_invalid_url(repository_client):
    response = repository_client.post(
        "/api/v1/repositories/analyze", json={"repository_url": "https://evil.test/a/b"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_missing_repository(repository_client):
    response = repository_client.get(f"/api/v1/repositories/{uuid4()}")
    assert response.status_code == 404


def test_unfinished_subresource(repository_client, app):
    app.state.store.get.return_value = SimpleNamespace(status="ANALYZING")
    response = repository_client.get(f"/api/v1/repositories/{uuid4()}/files")
    assert response.status_code == 409


def test_question_validation(repository_client):
    response = repository_client.post(
        f"/api/v1/repositories/{uuid4()}/ask", json={"question": "  "}
    )
    assert response.status_code == 422


def test_analyze_queues_once(repository_client, app, monkeypatch):
    repository_id = str(uuid4())
    monkeypatch.setattr(
        GitHubClient,
        "metadata",
        AsyncMock(
            return_value={
                "owner": {"login": "Owner"},
                "name": "Project",
                "description": "Test",
                "default_branch": "main",
            }
        ),
    )
    app.state.store.queue = AsyncMock(
        return_value=(SimpleNamespace(id=repository_id, status="QUEUED"), True)
    )
    submitted = []
    app.state.runner.submit = submitted.append
    response = repository_client.post(
        "/api/v1/repositories/analyze", json={"repository_url": "https://github.com/Owner/Project"}
    )
    assert response.status_code == 202
    assert response.json()["repository_id"] == repository_id
    assert submitted == [repository_id]
    app.state.store.queue.return_value = (SimpleNamespace(id=repository_id, status="QUEUED"), False)
    response = repository_client.post(
        "/api/v1/repositories/analyze", json={"repository_url": "https://github.com/owner/project"}
    )
    assert response.status_code == 200 and submitted == [repository_id]


def test_rate_limit_retry_header(repository_client, app):
    app.state.limiter.check("testclient", "analyze", 1, 3600)
    for _ in range(9):
        app.state.limiter.check("testclient", "analyze", 10, 3600)
    response = repository_client.post(
        "/api/v1/repositories/analyze", json={"repository_url": "https://github.com/a/b"}
    )
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0
