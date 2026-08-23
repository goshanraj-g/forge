"""Decision policies compared by the evaluation runner."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from backend.agent.models import AgentDecisionRecord
from backend.evaluation.models import EvaluationScenario
from backend.simulator.events import BaseEvent
from backend.simulator.state import FactoryState


class EvaluationPolicy(Protocol):
    name: str
    model_calls: int
    model_cost: float

    def should_replan(
        self,
        state: FactoryState,
        event: BaseEvent,
        scenario: EvaluationScenario,
    ) -> bool: ...


class NoOpPolicy:
    name = "no-op"
    model_calls = 0
    model_cost = 0.0

    def should_replan(
        self,
        state: FactoryState,
        event: BaseEvent,
        scenario: EvaluationScenario,
    ) -> bool:
        return False


class AlwaysReplanPolicy:
    name = "always-replan"
    model_calls = 0
    model_cost = 0.0

    def should_replan(
        self,
        state: FactoryState,
        event: BaseEvent,
        scenario: EvaluationScenario,
    ) -> bool:
        return True


class OraclePolicy:
    """Use scenario ground truth to replan only after material events."""

    name = "oracle"
    model_calls = 0
    model_cost = 0.0

    def should_replan(
        self,
        state: FactoryState,
        event: BaseEvent,
        scenario: EvaluationScenario,
    ) -> bool:
        return event.id in scenario.oracle_replan_event_ids


Investigator = Callable[[FactoryState, BaseEvent], AgentDecisionRecord]


class AgentPolicy:
    """Adapt the real agent investigation boundary to an evaluation policy."""

    name = "agent"

    def __init__(self, investigator: Investigator) -> None:
        self._investigator = investigator
        self.model_calls = 0
        self.model_cost = 0.0
        self.records: list[AgentDecisionRecord] = []

    def should_replan(
        self,
        state: FactoryState,
        event: BaseEvent,
        scenario: EvaluationScenario,
    ) -> bool:
        del scenario
        record = self._investigator(state, event)
        self.model_calls += 1
        self.records.append(record)
        return record.decision.should_replan


BASELINE_POLICIES: tuple[EvaluationPolicy, ...] = (
    NoOpPolicy(),
    AlwaysReplanPolicy(),
    OraclePolicy(),
)
