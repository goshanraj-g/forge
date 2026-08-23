from collections.abc import Callable
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from backend.agent.models import (
    AgentDecision,
    AgentDecisionRecord,
    DecisionSeverity,
    DecisionStatus,
)
from backend.evaluation.models import EvaluationMetrics, EvaluationResult
from backend.persistence.database import build_engine, create_schema
from backend.persistence.repository import PersistenceBatch, SQLRepository
from backend.simulator.events import MachineFailureEvent
from backend.simulator.seed import factory_01


@pytest.fixture
def sessions(tmp_path: Path) -> Callable[[], Session]:
    engine = build_engine(f"sqlite:///{tmp_path / 'repository.db'}")
    create_schema(engine)
    return lambda: Session(engine)


def test_repository_round_trips_latest_factory_snapshot(
    sessions: Callable[[], Session],
) -> None:
    repository = SQLRepository(sessions)
    first = factory_01()
    second = first.clone()
    second.sim_hour = 2

    repository.save(PersistenceBatch(state=first))
    repository.save(PersistenceBatch(state=first))
    repository.save(PersistenceBatch(state=second))

    loaded = repository.latest_snapshot("factory_01")
    assert loaded is not None
    assert loaded.snapshot_hash() == second.snapshot_hash()
    assert repository.latest_snapshot("unknown") is None


def test_repository_stores_all_artifact_types_atomically(
    sessions: Callable[[], Session],
) -> None:
    repository = SQLRepository(sessions)
    state = factory_01()
    event = MachineFailureEvent(
        id="event-001",
        sim_hour=0,
        machine_id="M1",
        duration_hours=2,
    )
    decision = AgentDecisionRecord(
        factory_name=state.name,
        simulation_hour=0,
        schedule_version=0,
        state_snapshot_hash=state.snapshot_hash(),
        trigger_event_id=event.id,
        trigger_event_type=str(event.type),
        prompt_version="test",
        model_name="test-model",
        decision=AgentDecision(
            status=DecisionStatus.NO_ACTION,
            severity=DecisionSeverity.INFO,
            summary="No action required.",
            explanation="The test event does not affect work.",
        ),
    )
    evaluation = EvaluationResult(
        scenario_id="scenario-001",
        policy_name="no-op",
        scenario_hash="scenario-hash",
        initial_state_hash=state.snapshot_hash(),
        final_state_hash=state.snapshot_hash(),
        metrics=EvaluationMetrics(),
    )

    repository.save(
        PersistenceBatch(
            state=state,
            events=[event],
            schedule=[],
            decision=decision,
            evaluation=evaluation,
        )
    )

    assert repository.latest_snapshot(state.name) is not None


def test_failed_batch_rolls_back_its_snapshot(
    sessions: Callable[[], Session],
) -> None:
    repository = SQLRepository(sessions)
    state = factory_01()
    event = MachineFailureEvent(
        id="duplicate-event",
        sim_hour=1,
        machine_id="M1",
        duration_hours=2,
    )

    with pytest.raises(IntegrityError):
        repository.save(PersistenceBatch(state=state, events=[event, event]))

    assert repository.latest_snapshot(state.name) is None


def test_event_can_be_recorded_when_scheduled_and_applied(
    sessions: Callable[[], Session],
) -> None:
    repository = SQLRepository(sessions)
    state = factory_01()
    event = MachineFailureEvent(
        id="event-lifecycle",
        sim_hour=1,
        machine_id="M1",
        duration_hours=2,
    )

    repository.save(
        PersistenceBatch(
            factory_name=state.name,
            events=[event],
            event_stage="scheduled",
        )
    )
    repository.save(PersistenceBatch(state=state, events=[event]))


def test_reset_clears_events_before_the_new_run(
    sessions: Callable[[], Session],
) -> None:
    repository = SQLRepository(sessions)
    state = factory_01()
    event = MachineFailureEvent(
        id="event-before-reset",
        sim_hour=1,
        machine_id="M1",
        duration_hours=2,
    )
    repository.save(
        PersistenceBatch(
            factory_name=state.name,
            events=[event],
            event_stage="scheduled",
        )
    )

    repository.save(PersistenceBatch(state=state, reset_factory=True))

    recovered = repository.recover_factory(state.name)
    assert recovered is not None
    assert recovered.pending == []
    assert recovered.log == []


def test_schedule_requires_its_factory_state(
    sessions: Callable[[], Session],
) -> None:
    repository = SQLRepository(sessions)

    with pytest.raises(ValueError, match="state is required"):
        repository.save(PersistenceBatch(schedule=[]))


def test_recovery_restores_pending_and_applied_event_lifecycles(
    sessions: Callable[[], Session],
) -> None:
    repository = SQLRepository(sessions)
    state = factory_01()
    pending = MachineFailureEvent(
        id="event-pending",
        sim_hour=4,
        machine_id="M1",
        duration_hours=2,
    )
    applied = MachineFailureEvent(
        id="event-applied",
        sim_hour=2,
        machine_id="M2",
        duration_hours=1,
    )
    repository.save(PersistenceBatch(state=state))
    repository.save(
        PersistenceBatch(
            factory_name=state.name,
            events=[pending],
            event_stage="scheduled",
        )
    )
    repository.save(PersistenceBatch(factory_name=state.name, events=[applied]))

    recovery = repository.recover_factory(state.name)

    assert recovery is not None
    assert [event.id for event in recovery.pending] == ["event-pending"]
    assert [event.id for event in recovery.log] == ["event-applied"]
