import asyncio

from pydantic_ai import models
from pydantic_ai.models.test import TestModel

from backend.agent.decision_agent import decision_agent
from backend.agent.dependencies import AgentDependencies
from backend.agent.models import AgentDecision
from backend.agent.service import investigate_factory
from backend.simulator.seed import factory_01

models.ALLOW_MODEL_REQUESTS = False


def test_agent_returns_typed_decision() -> None:
    state = factory_01()
    dependencies = AgentDependencies.from_state(state)

    result = decision_agent.run_sync(
        "Investigate the current factory state.",
        deps=dependencies,
        model=TestModel(),
    )

    assert isinstance(result.output, AgentDecision)


def test_agent_cannot_mutate_live_state() -> None:
    state = factory_01()
    original_hash = state.snapshot_hash()
    dependencies = AgentDependencies.from_state(state)

    decision_agent.run_sync(
        "Inspect every available source of factory information.",
        deps=dependencies,
        model=TestModel(),
    )

    assert state.snapshot_hash() == original_hash
    assert dependencies.state is not state


def test_investigation_service_returns_decision_without_mutation() -> None:
    state = factory_01()
    original_hash = state.snapshot_hash()

    decision = asyncio.run(
        investigate_factory(
            state,
            "Determine whether current operations require replanning.",
            TestModel(),
        )
    )

    assert isinstance(decision, AgentDecision)
    assert state.snapshot_hash() == original_hash
