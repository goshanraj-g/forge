"""Core factory domain models"""

from __future__ import annotations
from enum import StrEnum

from pydantic import BaseModel, Field, NonNegativeFloat, NonNegativeInt

PRECISION = 6

def q(value: float) -> float:
    return round(value, PRECISION)

class MachineStatus(StrEnum):
    RUNNING = "running"
    IDLE = "idle"
    DOWN = "down"
    MAINTENANCE = "maintenance"

class OrderStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    LATE = "late"

class ShipmentStatus(StrEnum):
    IN_TRANSIT = "in_transit"
    DELAYED = "delayed"
    RECEIVED = "received"
    
class Machine(BaseModel):
    id: str
    name: str
    capacity_per_hour: NonNegativeFloat
    supported_products: list[str]
    changeover_minutes: NonNegativeInt = 0
    status: MachineStatus = MachineStatus.IDLE
    down_until_hour: float | None = None
    current_family: str | None = None

    def can_produce(self, product_id: str) -> bool:
        return product_id in self.supported_products

    def is_available(self) -> bool:
        return self.status in (
            MachineStatus.RUNNING,
            MachineStatus.IDLE,
        )

class Product(BaseModel):
    id: str
    name: str
    family: str
    bom: dict[str, float] = Field(default_factory=dict)
    unit_cost: NonNegativeFloat = 0.0