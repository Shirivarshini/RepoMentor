"""Test configuration. Set the environment before any application module is imported."""

import os
from collections.abc import Iterator

# Assigned (not setdefault) so a developer's real environment can never leak into tests.
os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test-password@localhost:5432/test"
os.environ["ENVIRONMENT"] = "development"
os.environ["LOG_LEVEL"] = "INFO"
os.environ["CORS_ALLOWED_ORIGINS"] = "http://localhost:5173"

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_settings() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
