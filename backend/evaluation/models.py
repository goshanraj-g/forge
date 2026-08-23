"""Typed inputs and outputs for repeatable policy evaluations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Self

from pydantic import BaseModel, Field, PositiveFloat, model_validator

from backend.simulator.events import FactoryEvent


class EvaluationScenario(BaseModel):
    id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    factory_name: str
    horizon_hour: PositiveFloat
    step_hours: PositiveFloat = 0.25
    order_ids: list[str] = Field(default_factory=list)
    events: list[FactoryEvent] = Field(default_factory=list)
    oracle_replan_event_ids: set[str] = Field(default_factory=set)

    @model_validator(mode="after")
    def validate_event_stream(self) -> Self:
        event_ids = [event.id for event in self.events]
        if any(not event_id for event_id in event_ids):
            raise ValueError("scenario events require stable ids")
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("scenario event ids must be unique")
        if self.events != sorted(self.events, key=lambda event: event.sort_key):
            raise ValueError("scenario events must be ordered")
        if any(event.sim_hour > self.horizon_hour for event in self.events):
            raise ValueError("scenario events must occur within the horizon")
        evaluation_hours = [event.sim_hour for event in self.events]
        evaluation_hours.append(self.horizon_hour)
        if any(
            abs(hour / self.step_hours - round(hour / self.step_hours)) > 1e-9
            for hour in evaluation_hours
        ):
            raise ValueError("event and horizon hours must align with step_hours")

        unknown_oracle_ids = self.oracle_replan_event_ids - set(event_ids)
        if unknown_oracle_ids:
            raise ValueError(
                f"oracle replan ids do not exist: {sorted(unknown_oracle_ids)}"
            )
        return self


class EvaluationMetrics(BaseModel):
    late_orders: int = 0
    priority_weighted_lateness: float = 0.0
    production_cost: float = 0.0
    penalty_cost: float = 0.0
    total_cost: float = 0.0
    overtime_hours: float = 0.0
    constraint_violations: int = 0
    replans: int = 0
    model_calls: int = 0
    model_cost: float = 0.0


class EvaluationDecisionTrace(BaseModel):
    event_id: str
    event_type: str
    simulation_hour: float
    state_snapshot_hash: str
    replan_requested: bool
    schedule_committed: bool
    resulting_schedule_version: int


class EvaluationResult(BaseModel):
    scenario_id: str
    policy_name: str
    scenario_hash: str
    initial_state_hash: str
    final_state_hash: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metrics: EvaluationMetrics
    decision_event_ids: list[str] = Field(default_factory=list)
    schedule_versions: list[int] = Field(default_factory=list)
    decisions: list[EvaluationDecisionTrace] = Field(default_factory=list)

    def deterministic_payload(self) -> dict[str, object]:
        """Return result data that must match between repeated runs."""
        return self.model_dump(mode="json", exclude={"started_at"})
