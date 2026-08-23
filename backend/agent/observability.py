"""Langfuse tracing for agent runs"""

import os

from langfuse import get_client
from pydantic_ai import Agent


def enable_pydantic_ai_instrumentation() -> None:
    Agent.instrument_all()


def configure_agent_observability() -> bool:
    required_values = (
        os.getenv("LANGFUSE_PUBLIC_KEY"),
        os.getenv("LANGFUSE_SECRET_KEY"),
        os.getenv("LANGFUSE_BASE_URL"),
    )

    if not all(required_values):
        return False

    get_client()
    enable_pydantic_ai_instrumentation()
    return True
