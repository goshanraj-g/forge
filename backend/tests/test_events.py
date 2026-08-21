import pytest
from pydantic import TypeAdapter, ValidationError

from backend.simulator.events import (
    INJECTABLE_EVENT_TYPES,
    EventType,
    FactoryEvent,
    MachineFailureEvent,
    MachineRepairEvent,
    OrderCompleteEvent,
    SupplierDelayEvent,
    UrgentOrderEvent,
    sort_events,
)


def test_event_type_and_sort_key_are_explicit() -> None:
    event = MachineFailureEvent(
        id="E1",
        sim_hour=12,
        machine_id="M2",
        duration_hours=8,
    )

    assert event.type == EventType.MACHINE_FAILURE
    assert event.sort_key == (12, "machine_failure", "E1")


@pytest.mark.parametrize("duration", [0, -1])
def test_failure_requires_positive_duration(duration: float) -> None:
    with pytest.raises(ValidationError):
        MachineFailureEvent(
            sim_hour=12,
            machine_id="M2",
            duration_hours=duration,
        )


def test_factory_event_uses_type_discriminator() -> None:
    event: FactoryEvent = TypeAdapter(FactoryEvent).validate_python(
        {
            "type": "urgent_order",
            "id": "E2",
            "sim_hour": 4,
            "product_id": "P1",
            "quantity": 25,
            "due_hour": 10,
        },
    )

    assert isinstance(event, UrgentOrderEvent)
    assert event.priority == 1


def test_events_have_stable_total_order() -> None:
    events = [
        MachineRepairEvent(id="E3", sim_hour=5, machine_id="M1"),
        SupplierDelayEvent(
            id="E2",
            sim_hour=2,
            shipment_id="SH1",
            delay_hours=3,
        ),
        MachineRepairEvent(id="E1", sim_hour=5, machine_id="M2"),
    ]

    assert [event.id for event in sort_events(events)] == ["E2", "E1", "E3"]


def test_only_external_events_are_injectable() -> None:
    assert EventType.MACHINE_FAILURE in INJECTABLE_EVENT_TYPES
    assert EventType.URGENT_ORDER in INJECTABLE_EVENT_TYPES
    assert EventType.ORDER_COMPLETE not in INJECTABLE_EVENT_TYPES

    derived = OrderCompleteEvent(
        id="E4",
        sim_hour=8,
        order_id="O1",
        hours_late=0,
    )
    assert derived.type == EventType.ORDER_COMPLETE
