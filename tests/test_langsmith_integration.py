"""Tests for LangSmith configuration wiring."""

from cloudy_intell.config.settings import AppSettings
from cloudy_intell.services.architecture_service import build_graph_run_config


def test_langsmith_settings_load_from_env(monkeypatch) -> None:
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-key")
    monkeypatch.setenv("LANGSMITH_PROJECT", "studio-project")
    monkeypatch.setenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")

    settings = AppSettings()

    assert settings.langsmith_tracing is True
    assert settings.langsmith_api_key == "test-key"
    assert settings.langsmith_project == "studio-project"
    assert settings.langsmith_endpoint == "https://api.smith.langchain.com"


def test_build_graph_run_config_contains_metadata() -> None:
    config = build_graph_run_config(
        thread_id="cloudy-intell-123",
        run_label="local-run",
        langsmith_project="cloudy-intell",
    )

    assert config["configurable"]["thread_id"] == "cloudy-intell-123"
    assert config["run_name"].startswith("local-run-")
    assert "cloudy-intell" in config["tags"]
    assert config["metadata"]["thread_id"] == "cloudy-intell-123"
    assert config["metadata"]["run_label"] == "local-run"
    assert config["metadata"]["langsmith_project"] == "cloudy-intell"
