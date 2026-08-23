"""Langfuse tracing for agent runs"""

import os

import structlog
from langfuse import Langfuse, get_client
from pydantic_ai import Agent

logger = structlog.get_logger(__name__)


def enable_pydantic_ai_instrumentation() -> None:
    Agent.instrument_all()


def _credentials_accepted(client: Langfuse, base_url: str) -> bool:
    """Check the keys once instead of learning they are wrong per span batch.

    Langfuse Cloud is split by region and a key pair is only valid against the
    region that issued it. Without this check a host mismatch is invisible at
    startup and then repeats forever as "Failed to export span batch code: 401".
    """
    try:
        accepted = client.auth_check()
    except Exception as error:
        logger.warning(
            "langfuse_auth_check_failed",
            base_url=base_url,
            error=str(error),
        )
        accepted = False

    if accepted:
        return True

    logger.warning(
        "langfuse_tracing_disabled",
        base_url=base_url,
        reason="credentials rejected by the configured host",
    )
    client.shutdown()
    return False


def configure_agent_observability() -> bool:
    base_url = os.getenv("LANGFUSE_BASE_URL")
    required_values = (
        os.getenv("LANGFUSE_PUBLIC_KEY"),
        os.getenv("LANGFUSE_SECRET_KEY"),
        base_url,
    )

    if not all(required_values):
        return False

    client = get_client()
    if not _credentials_accepted(client, str(base_url)):
        return False

    enable_pydantic_ai_instrumentation()
    return True
