from unittest.mock import Mock

import pytest

from backend.agent import observability


def clear_langfuse_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "LANGFUSE_BASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)


def test_observability_stays_disabled_without_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_langfuse_environment(monkeypatch)
    get_client = Mock()
    enable_instrumentation = Mock()
    monkeypatch.setattr(observability, "get_client", get_client)
    monkeypatch.setattr(
        observability,
        "enable_pydantic_ai_instrumentation",
        enable_instrumentation,
    )

    configured = observability.configure_agent_observability()

    assert configured is False
    get_client.assert_not_called()
    enable_instrumentation.assert_not_called()


def test_observability_initializes_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "test-public-key")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "https://langfuse.example.com")
    get_client = Mock()
    enable_instrumentation = Mock()
    monkeypatch.setattr(observability, "get_client", get_client)
    monkeypatch.setattr(
        observability,
        "enable_pydantic_ai_instrumentation",
        enable_instrumentation,
    )

    configured = observability.configure_agent_observability()

    assert configured is True
    get_client.assert_called_once_with()
    enable_instrumentation.assert_called_once_with()
