"""Environment-based config for production agent runs"""

import os
from dataclasses import dataclass
from math import isfinite

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

        timeout_value = os.getenv("FORGEOPS_AGENT_TIMEOUT_SECONDS", "30")
        try:
            timeout_seconds = float(timeout_value)
        except ValueError as error:
            raise RuntimeError(
                "FORGEOPS_AGENT_TIMEOUT_SECONDS must be a number"
            ) from error
        if not isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise RuntimeError(
                "FORGEOPS_AGENT_TIMEOUT_SECONDS must be finite and positive"
            )

        return cls(model_name=model_name, timeout_seconds=timeout_seconds)


def build_production_model(
    settings: AgentSettings,
) -> Model:
    return OpenAIResponsesModel(settings.model_name)
