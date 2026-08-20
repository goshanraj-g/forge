"""Typed events that can change or describe factory state"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Union

from pydantic import (
    BaseModel,
    Field,
    NonNegativeFloat,
    PositiveFloat,
    PositiveInt,
)

class EventType(StrEnum):
    MACHINE_FAILURE = "machine_failure"
    MACHINE_REPAIR = "machine_repair"
    SUPPLIER_DELAY = "supplier_delay"
    URGENT_ORDER = "urgent_order"
    LOW_INVENTORY = "low_inventory"
    SHIPMENT_RECEIVED = "shipment_received"
    ORDER_COMPLETE = "order_complete"
    ORDER_LATE = "order_late"
    
class BaseEvent(BaseModel):
    id: str = ""
    sim_hour: NonNegativeFloat
    triggered_agent_run_id: str | None = None
    @property
    def sort_key(self) -> tuple[float, str, str]:
        return (self.sim_hour, str(self.type), self.id)


class MachineFailureEvent(BaseEvent):
    type: Literal[EventType.MACHINE_FAILURE] = EventType.MACHINE_FAILURE
    machine_id: str
    duration_hours: PositiveFloat


class MachineRepairEvent(BaseEvent):
    type: Literal[EventType.MACHINE_REPAIR] = EventType.MACHINE_REPAIR
    machine_id: str


class SupplierDelayEvent(BaseEvent):
    type: Literal[EventType.SUPPLIER_DELAY] = EventType.SUPPLIER_DELAY
    shipment_id: str
    delay_hours: PositiveFloat


class UrgentOrderEvent(BaseEvent):
    type: Literal[EventType.URGENT_ORDER] = EventType.URGENT_ORDER
    product_id: str
    quantity: PositiveInt
    due_hour: NonNegativeFloat
    priority: int = 1
    late_penalty_per_hour: NonNegativeFloat = 500.0
    order_id: str | None = None


class LowInventoryEvent(BaseEvent):
    type: Literal[EventType.LOW_INVENTORY] = EventType.LOW_INVENTORY
    component_id: str
    on_hand: NonNegativeFloat
    reorder_point: NonNegativeFloat


class ShipmentReceivedEvent(BaseEvent):
    type: Literal[EventType.SHIPMENT_RECEIVED] = EventType.SHIPMENT_RECEIVED
    shipment_id: str
    component_id: str
    quantity: PositiveFloat


class OrderCompleteEvent(BaseEvent):
    type: Literal[EventType.ORDER_COMPLETE] = EventType.ORDER_COMPLETE
    order_id: str
    hours_late: NonNegativeFloat


class OrderLateEvent(BaseEvent):
    type: Literal[EventType.ORDER_LATE] = EventType.ORDER_LATE
    order_id: str
    due_hour: NonNegativeFloat


FactoryEvent = Annotated[
    Union[
        MachineFailureEvent,
        MachineRepairEvent,
        SupplierDelayEvent,
        UrgentOrderEvent,
        LowInventoryEvent,
        ShipmentReceivedEvent,
        OrderCompleteEvent,
        OrderLateEvent,
    ],
    Field(discriminator="type"),
]


INJECTABLE_EVENT_TYPES = (
    EventType.MACHINE_FAILURE,
    EventType.MACHINE_REPAIR,
    EventType.SUPPLIER_DELAY,
    EventType.URGENT_ORDER,
)


def sort_events(events: list[BaseEvent]) -> list[BaseEvent]:
    """Sort events by simulation hour, type, and ID"""
    return sorted(events, key=lambda event: event.sort_key)