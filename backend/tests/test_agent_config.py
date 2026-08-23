import pytest
from pydantic_ai.models.openai import OpenAIResponsesModel

from backend.agent.config import AgentSettings, build_production_model


def test_settings_require_model_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FORGEOPS_AGENT_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="FORGEOPS_AGENT_MODEL"):
        AgentSettings.from_environment()


def test_settings_require_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORGEOPS_AGENT_MODEL", "test-model")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        AgentSettings.from_environment()


def test_builds_openai_responses_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORGEOPS_AGENT_MODEL", "test-model")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    settings = AgentSettings.from_environment()
    model = build_production_model(settings)

    assert settings.model_name == "test-model"
    assert settings.timeout_seconds == 30
    assert isinstance(model, OpenAIResponsesModel)
    assert model.model_name == "test-model"


def test_settings_reject_nonpositive_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORGEOPS_AGENT_MODEL", "test-model")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("FORGEOPS_AGENT_TIMEOUT_SECONDS", "0")

    with pytest.raises(RuntimeError, match="must be finite and positive"):
        AgentSettings.from_environment()


def test_settings_reject_nonnumeric_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORGEOPS_AGENT_MODEL", "test-model")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("FORGEOPS_AGENT_TIMEOUT_SECONDS", "invalid")

    with pytest.raises(RuntimeError, match="must be a number"):
        AgentSettings.from_environment()


def test_settings_reject_nonfinite_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORGEOPS_AGENT_MODEL", "test-model")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("FORGEOPS_AGENT_TIMEOUT_SECONDS", "nan")

    with pytest.raises(RuntimeError, match="must be finite and positive"):
        AgentSettings.from_environment()
