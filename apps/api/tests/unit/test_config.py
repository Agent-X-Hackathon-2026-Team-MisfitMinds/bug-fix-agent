from typing import Any

from config import Settings


def test_empty_env_values_fall_back_to_defaults(
    monkeypatch: Any, tmp_path: Any
) -> None:
    monkeypatch.chdir(tmp_path)  # no .env file in a bare directory
    monkeypatch.setenv("COOKIE_SECURE", "")
    monkeypatch.setenv("API_BASE_URL", "")
    monkeypatch.setenv("WEB_ORIGIN", "")

    settings = Settings()

    assert settings.cookie_secure is True
    assert settings.api_base_url == "http://localhost:8000"
    assert settings.web_origin == "http://localhost:3000"


def test_explicit_env_values_win(monkeypatch: Any, tmp_path: Any) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("API_BASE_URL", "https://api.example.com")

    settings = Settings()

    assert settings.cookie_secure is False
    assert settings.api_base_url == "https://api.example.com"
