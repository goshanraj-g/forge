"""Request and response models for the API"""

from typing import Annotated

from pydantic import (
    BaseModel,
    Field,
    FiniteFloat,
    NonNegativeInt,
    SerializeAsAny,
)

from backend.evaluation.models import EvaluationResult
from backend.optimizer.models import ValidationResult
from backend.simulator.events import BaseEvent
from backend.simulator.models import ProductionJob
from backend.simulator.state import FactoryState

PositiveFiniteFloat = Annotated[FiniteFloat, Field(gt=0)]
NonNegativeFiniteFloat = Annotated[FiniteFloat, Field(ge=0)]


class TickRequest(BaseModel):
    step_hours: PositiveFiniteFloat | None = None


class SimulationResponse(BaseModel):
    state: FactoryState
    events: list[SerializeAsAny[BaseEvent]]


class RunUntilRequest(BaseModel):
    hour: NonNegativeFiniteFloat
    step_hours: PositiveFiniteFloat | None = None


class EventScheduledResponse(BaseModel):
    event: SerializeAsAny[BaseEvent]
    pending_event_count: int


class InvestigateEventRequest(BaseModel):
    event_id: str = Field(min_length=1)


class CommitScheduleRequest(BaseModel):
    expected_version: NonNegativeInt
    jobs: list[ProductionJob]
    hard_deadline_orders: list[str] = Field(default_factory=list)


class CommitScheduleResponse(BaseModel):
    state: FactoryState
    validation: ValidationResult


class EvaluationScenarioSummary(BaseModel):
    id: str
    description: str
    factory_name: str
    horizon_hour: float
    scenario_hash: str
    event_count: int


class EvaluationComparisonResponse(BaseModel):
    """Every baseline policy run against every scenario, plus scenario metadata."""

    scenarios: list[EvaluationScenarioSummary]
    results: list[EvaluationResult]
