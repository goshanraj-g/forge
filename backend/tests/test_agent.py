import asyncio

from pydantic_ai import models
from pydantic_ai.models.test import TestModel

from backend.agent.decision_agent import decision_agent
from backend.agent.dependencies import AgentDependencies
from backend.agent.models import AgentDecision
from backend.agent.service import investigate_event, investigate_factory
from backend.simulator.events import MachineFailureEvent
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


def test_event_investigation_creates_auditable_record() -> None:
    state = factory_01()
    original_hash = state.snapshot_hash()
    event = MachineFailureEvent(
        id="evt-test-001",
        sim_hour=state.sim_hour,
        machine_id="M1",
        duration_hours=2,
    )

    record = asyncio.run(
        investigate_event(
            state,
            event,
            TestModel(),
        )
    )

    assert record.factory_name == state.name
    assert record.simulation_hour == state.sim_hour
    assert record.schedule_version == state.schedule_version
    assert record.state_snapshot_hash == original_hash
    assert record.trigger_event_id == event.id
    assert record.trigger_event_type == "machine_failure"
    assert isinstance(record.decision, AgentDecision)
    assert state.snapshot_hash() == original_hash
