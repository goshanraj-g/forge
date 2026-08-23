"""Atomic persistence boundary for ForgeOps domain artifacts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from pydantic import TypeAdapter
from sqlmodel import Session, col, select

from backend.agent.models import AgentDecisionRecord
from backend.evaluation.models import EvaluationResult
from backend.persistence.tables import (
    DecisionRecordRow,
    EvaluationRecordRow,
    EventRecordRow,
    FactorySnapshotRow,
    ScheduleRecordRow,
)
from backend.simulator.events import BaseEvent, FactoryEvent, sort_events
from backend.simulator.models import ProductionJob
from backend.simulator.state import FactoryState


@dataclass(frozen=True)
class PersistenceBatch:
    factory_name: str | None = None
    state: FactoryState | None = None
    events: list[BaseEvent] = field(default_factory=list)
    event_stage: str = "applied"
    schedule: list[ProductionJob] | None = None
    decision: AgentDecisionRecord | None = None
    evaluation: EvaluationResult | None = None


@dataclass(frozen=True)
class FactoryRecovery:
    state: FactoryState
    pending: list[BaseEvent]
    log: list[BaseEvent]


EVENT_ADAPTER: TypeAdapter[FactoryEvent] = TypeAdapter(FactoryEvent)


class Repository(Protocol):
    def save(self, batch: PersistenceBatch) -> None: ...

    def latest_snapshot(self, factory_name: str) -> FactoryState | None: ...

    def recover_factory(self, factory_name: str) -> FactoryRecovery | None: ...


class SQLRepository:
    def __init__(self, sessions: Callable[[], Session]) -> None:
        self._sessions = sessions

    def save(self, batch: PersistenceBatch) -> None:
        """Commit every supplied artifact together or roll all of them back."""
        with self._sessions() as session, session.begin():
            state = batch.state
            factory_name = state.name if state is not None else batch.factory_name
            if batch.schedule is not None and state is None:
                raise ValueError("state is required to save a schedule")
            if state is not None:
                session.add(
                    FactorySnapshotRow(
                        factory_name=state.name,
                        simulation_hour=state.sim_hour,
                        schedule_version=state.schedule_version,
                        snapshot_hash=state.snapshot_hash(),
                        payload=state.model_dump(mode="json"),
                    )
                )
                if batch.schedule is not None:
                    session.add(
                        ScheduleRecordRow(
                            factory_name=state.name,
                            schedule_version=state.schedule_version,
                            state_snapshot_hash=state.snapshot_hash(),
                            payload={
                                "jobs": [
                                    job.model_dump(mode="json")
                                    for job in batch.schedule
                                ]
                            },
                        )
                    )

            if batch.events and factory_name is None:
                raise ValueError("factory_name or state is required to save events")
            for event in batch.events:
                session.add(
                    EventRecordRow(
                        factory_name=str(factory_name),
                        event_id=event.id,
                        event_type=str(event.type),
                        event_stage=batch.event_stage,
                        simulation_hour=event.sim_hour,
                        payload=event.model_dump(mode="json"),
                    )
                )

            if batch.decision is not None:
                decision = batch.decision
                session.add(
                    DecisionRecordRow(
                        factory_name=decision.factory_name,
                        trigger_event_id=decision.trigger_event_id,
                        state_snapshot_hash=decision.state_snapshot_hash,
                        prompt_version=decision.prompt_version,
                        model_name=decision.model_name,
                        payload=decision.model_dump(mode="json"),
                    )
                )

            if batch.evaluation is not None:
                result = batch.evaluation
                session.add(
                    EvaluationRecordRow(
                        scenario_id=result.scenario_id,
                        policy_name=result.policy_name,
                        scenario_hash=result.scenario_hash,
                        final_state_hash=result.final_state_hash,
                        payload=result.model_dump(mode="json"),
                    )
                )

    def latest_snapshot(self, factory_name: str) -> FactoryState | None:
        with self._sessions() as session:
            statement = (
                select(FactorySnapshotRow)
                .where(FactorySnapshotRow.factory_name == factory_name)
                .order_by(col(FactorySnapshotRow.sequence).desc())
            )
            row = session.exec(statement).first()
            return FactoryState.model_validate(row.payload) if row is not None else None

    def recover_factory(self, factory_name: str) -> FactoryRecovery | None:
        state = self.latest_snapshot(factory_name)
        if state is None:
            return None
        with self._sessions() as session:
            rows = session.exec(
                select(EventRecordRow).where(
                    EventRecordRow.factory_name == factory_name
                )
            ).all()

        scheduled: dict[str, BaseEvent] = {}
        applied: dict[str, BaseEvent] = {}
        for row in rows:
            event = EVENT_ADAPTER.validate_python(row.payload)
            if row.event_stage == "scheduled":
                scheduled[row.event_id] = event
            elif row.event_stage == "applied":
                applied[row.event_id] = event
        pending = [event for key, event in scheduled.items() if key not in applied]
        return FactoryRecovery(
            state=state,
            pending=sort_events(pending),
            log=sort_events(list(applied.values())),
        )
