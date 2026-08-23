"""Environment-based config for production agent runs"""

import os
from dataclasses import dataclass

from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIResponsesModel


@dataclass(frozen=True)
class AgentSettings:
    model_name: str

    @classmethod
    def from_environment(cls) -> "AgentSettings":
        model_name = os.getenv("FORGEOPS_AGENT_MODEL")
        if not model_name:
            raise RuntimeError("FORGEOPS_AGENT_MODEL is not configured")

        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is not configured")

        return cls(model_name=model_name)


def build_production_model(
    settings: AgentSettings,
) -> Model:
    return OpenAIResponsesModel(settings.model_name)
