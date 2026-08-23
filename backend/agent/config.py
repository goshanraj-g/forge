"""Environment-based config for production agent runs"""

import os
from dataclasses import dataclass

from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIResponsesModel


@dataclass(frozen=True)
class AgentSettings:
    model_name: str
    timeout_seconds: float = 30.0

    @classmethod
    def from_environment(cls) -> "AgentSettings":
        model_name = os.getenv("FORGEOPS_AGENT_MODEL")
        if not model_name:
            raise RuntimeError("FORGEOPS_AGENT_MODEL is not configured")

        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is not configured")

        timeout_seconds = float(os.getenv("FORGEOPS_AGENT_TIMEOUT_SECONDS", "30"))
        if timeout_seconds <= 0:
            raise RuntimeError("FORGEOPS_AGENT_TIMEOUT_SECONDS must be positive")

        return cls(model_name=model_name, timeout_seconds=timeout_seconds)


def build_production_model(
    settings: AgentSettings,
) -> Model:
    return OpenAIResponsesModel(settings.model_name)
