import pytest
from pydantic import ValidationError

from app.core.config import Settings


def make(**overrides: object) -> Settings:
    values: dict[str, object] = {"database_url": "postgresql+asyncpg://u:pw@db:5432/app"}
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_defaults() -> None:
    settings = make()
    assert settings.environment == "development"
    assert settings.log_level == "INFO"
    assert settings.cors_origins == ["http://localhost:5173"]
    assert settings.docs_enabled is True


@pytest.mark.parametrize("prefix", ["postgresql://", "postgres://"])
def test_plain_postgres_urls_select_asyncpg(prefix: str) -> None:
    settings = make(database_url=f"{prefix}u:pw@db:5432/app")
    assert settings.database_url.get_secret_value() == "postgresql+asyncpg://u:pw@db:5432/app"


def test_database_url_is_hidden_in_repr() -> None:
    assert "pw" not in repr(make())


def test_invalid_database_url_is_rejected_without_leaking_the_password() -> None:
    with pytest.raises(ValidationError) as excinfo:
        make(database_url="mysql://user:super-secret-pw@db/app")
    assert "super-secret-pw" not in str(excinfo.value)


def test_database_url_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_cors_origins_are_parsed_from_comma_separated_text() -> None:
    settings = make(cors_allowed_origins=" http://a.test , http://b.test,, ")
    assert settings.cors_origins == ["http://a.test", "http://b.test"]


def test_log_level_is_case_insensitive() -> None:
    assert make(log_level="debug").log_level == "DEBUG"


def test_wildcard_cors_is_rejected_in_production() -> None:
    with pytest.raises(ValidationError):
        make(environment="production", cors_allowed_origins="*")


def test_docs_are_disabled_outside_development() -> None:
    assert make(environment="production").docs_enabled is False
