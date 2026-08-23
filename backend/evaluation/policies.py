"""Decision policies compared by the evaluation runner."""

from __future__ import annotations

from typing import Protocol

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


BASELINE_POLICIES: tuple[EvaluationPolicy, ...] = (
    NoOpPolicy(),
    AlwaysReplanPolicy(),
    OraclePolicy(),
)
