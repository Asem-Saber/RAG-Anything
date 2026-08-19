import pytest

from rag_anything.settings import Settings, get_settings


def test_defaults_are_dev_safe() -> None:
    settings = Settings(_env_file=None)
    assert settings.environment == "dev"
    assert settings.access_token_ttl_minutes == 15
    assert settings.refresh_token_ttl_days == 30
    assert settings.jwt_algorithm == "HS256"


def test_reads_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("JWT_SECRET", "s3cret-from-env")
    monkeypatch.setenv("ACCESS_TOKEN_TTL_MINUTES", "5")
    settings = Settings(_env_file=None)
    assert settings.environment == "prod"
    assert settings.jwt_secret.get_secret_value() == "s3cret-from-env"
    assert settings.access_token_ttl_minutes == 5


def test_unrelated_env_vars_are_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-whatever")
    Settings(_env_file=None)  


def test_secrets_do_not_appear_in_repr() -> None:
    settings = Settings(
        _env_file=None,
        jwt_secret="super-secret-value",
        postgres_password="another-secret",
    )
    assert "super-secret-value" not in repr(settings)
    assert "another-secret" not in repr(settings)


def test_database_url_is_assembled_from_components() -> None:
    settings = Settings(
        _env_file=None,
        postgres_host="db.example.com",
        postgres_port=5433,
        postgres_user="postgres",
        postgres_password="plainpassword",
        postgres_db="RAG-Anything",
    )
    assert settings.database_url == (
        "postgresql+asyncpg://postgres:plainpassword@db.example.com:5433/RAG-Anything"
    )


def test_special_characters_in_the_password_are_escaped() -> None:
    settings = Settings(_env_file=None, postgres_password="pa##word")
    assert "%23%23" in settings.database_url
    assert "#" not in settings.database_url


def test_the_escaped_url_still_parses_back_to_the_real_password() -> None:
    from sqlalchemy.engine import make_url

    password = "p@ss#word/with:specials?and space"
    settings = Settings(_env_file=None, postgres_password=password)
    assert make_url(settings.database_url).password == password


def test_dev_and_test_urls_differ_only_in_database() -> None:
    settings = Settings(
        _env_file=None, postgres_db="RAG-Anything", postgres_test_db="RAG-Anything-Test"
    )
    assert settings.database_url.endswith("/RAG-Anything")
    assert settings.test_database_url.endswith("/RAG-Anything-Test")


def test_get_settings_is_cached() -> None:
    get_settings.cache_clear()
    assert get_settings() is get_settings()