import pytest

from app.config import Settings


def test_llm_settings_come_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "http://fake-llm.test/v1")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://demo.example.test")

    settings = Settings(_env_file=None)

    assert settings.llm_base_url == "http://fake-llm.test/v1"
    assert settings.llm_api_key == "test-key"
    assert settings.llm_model == "fake-model"
    assert settings.frontend_origin == "https://demo.example.test"


def test_llm_settings_have_no_hardcoded_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(var, raising=False)

    settings = Settings(_env_file=None)

    assert (settings.llm_base_url, settings.llm_api_key, settings.llm_model) == ("", "", "")
