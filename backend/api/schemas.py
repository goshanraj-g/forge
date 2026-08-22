"""Request and response models for the API"""

from pydantic import (
    BaseModel,
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveFloat,
    SerializeAsAny,
)

from backend.optimizer.models import ValidationResult
from backend.simulator.events import BaseEvent
from backend.simulator.models import ProductionJob
from backend.simulator.state import FactoryState


class TickRequest(BaseModel):
    step_hours: PositiveFloat | None = None


class SimulationResponse(BaseModel):
    state: FactoryState
    events: list[SerializeAsAny[BaseEvent]]


class RunUntilRequest(BaseModel):
    hour: NonNegativeFloat
    step_hours: PositiveFloat | None = None


class EventScheduledResponse(BaseModel):
    event: SerializeAsAny[BaseEvent]
    pending_event_count: int


class CommitScheduleRequest(BaseModel):
    expected_version: NonNegativeInt
    jobs: list[ProductionJob]
    hard_deadline_orders: list[str] = Field(default_factory=list)


class CommitScheduleResponse(BaseModel):
    state: FactoryState
    validation: ValidationResult
