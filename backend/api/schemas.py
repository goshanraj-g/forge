"""Request and response models for the API"""

from pydantic import BaseModel, NonNegativeFloat, PositiveFloat, SerializeAsAny

from backend.simulator.events import BaseEvent
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
