"""Core factory domain models"""

from __future__ import annotations

from enum import StrEnum

from pydantic import (
    BaseModel,
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    model_validator,
)

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


class Order(BaseModel):
    id: str
    product_id: str
    quantity: NonNegativeInt
    due_hour: float
    priority: int = 3
    late_penalty_per_hour: NonNegativeFloat = 0.0
    status: OrderStatus = OrderStatus.PENDING
    produced: NonNegativeFloat = 0.0
    completed_hour: float | None = None

    @property
    def remaining(self) -> float:
        return q(max(0.0, self.quantity - self.produced))

    def is_open(self) -> bool:
        return self.status in (
            OrderStatus.PENDING,
            OrderStatus.IN_PROGRESS,
        )


class InventoryItem(BaseModel):
    component_id: str
    on_hand: NonNegativeFloat = 0.0
    reserved: NonNegativeFloat = 0.0
    reorder_point: NonNegativeFloat = 0.0

    @property
    def available(self) -> float:
        return q(max(0.0, self.on_hand - self.reserved))


class Supplier(BaseModel):
    id: str
    component_id: str
    lead_time_hours: NonNegativeFloat
    reliability: float = 1.0


class Shipment(BaseModel):
    id: str
    supplier_id: str
    component_id: str
    quantity: NonNegativeFloat
    eta_hour: float
    status: ShipmentStatus = ShipmentStatus.IN_TRANSIT


class ProductionJob(BaseModel):
    id: str
    order_id: str
    machine_id: str
    product_id: str
    start_hour: float
    end_hour: float
    quantity: NonNegativeInt
    schedule_version: int = 0
    produced: NonNegativeFloat = 0.0

    @model_validator(mode="after")
    def validate_duration(self) -> ProductionJob:
        if self.end_hour <= self.start_hour:
            raise ValueError("end_hour must be greater than start_hour")
        return self

    def is_active_at(self, hour: float) -> bool:
        return self.start_hour <= hour < self.end_hour
