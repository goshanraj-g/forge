import pytest

from backend.simulator import events as ev
from backend.simulator.engine import (
    FactorySimulator,
    SimulationContext,
    overtime_overlap,
)
from backend.simulator.models import (
    InventoryItem,
    Machine,
    MachineStatus,
    Order,
    OrderStatus,
    Product,
    ProductionJob,
    Shipment,
    ShipmentStatus,
)
from backend.simulator.state import FactoryState


def production_state() -> FactoryState:
    return FactoryState(
        machines={
            "M1": Machine(
                id="M1",
                name="Line 1",
                capacity_per_hour=10,
                supported_products=["P1"],
                current_family="family",
            ),
        },
        products={
            "P1": Product(
                id="P1",
                name="Product 1",
                family="family",
                bom={"C1": 1},
                unit_cost=2,
            ),
        },
        orders={
            "O1": Order(
                id="O1",
                product_id="P1",
                quantity=10,
                due_hour=4,
            ),
        },
        inventory={
            "C1": InventoryItem(
                component_id="C1",
                on_hand=20,
                reorder_point=5,
            ),
        },
        jobs={
            "J1": ProductionJob(
                id="J1",
                order_id="O1",
                machine_id="M1",
                product_id="P1",
                start_hour=0,
                end_hour=2,
                quantity=10,
            ),
        },
    )


def test_context_generates_repeatable_ids_and_rejects_bad_steps() -> None:
    context = SimulationContext(seed=7)

    assert context.next_id("evt") == "evt-00001"
    assert context.next_id("evt") == "evt-00002"

    with pytest.raises(ValueError, match="step_hours must be positive"):
        SimulationContext(step_hours=0)


def test_overtime_overlap_repeats_each_day() -> None:
    assert overtime_overlap(15, 17) == 1
    assert overtime_overlap(23, 25) == 1
    assert overtime_overlap(39, 41) == 1
    assert overtime_overlap(10, 12) == 0


def test_external_events_change_state_and_are_logged() -> None:
    state = production_state()
    simulator = FactorySimulator(state)

    simulator.apply_event(
        ev.MachineFailureEvent(
            sim_hour=2,
            machine_id="M1",
            duration_hours=3,
        ),
    )
    simulator.apply_event(
        ev.UrgentOrderEvent(
            sim_hour=2,
            order_id="O2",
            product_id="P1",
            quantity=5,
            due_hour=6,
        ),
    )

    assert state.machines["M1"].status == MachineStatus.DOWN
    assert state.machines["M1"].down_until_hour == 5
    assert state.orders["O2"].quantity == 5
    assert len(simulator.log) == 2


def test_tick_repairs_machine_and_receives_shipment() -> None:
    state = production_state()
    state.jobs.clear()
    state.machines["M1"].status = MachineStatus.DOWN
    state.machines["M1"].down_until_hour = 1
    state.shipments["SH1"] = Shipment(
        id="SH1",
        supplier_id="S1",
        component_id="C1",
        quantity=5,
        eta_hour=1,
    )
    simulator = FactorySimulator(state)

    emitted = simulator.tick(1)

    assert state.machines["M1"].status == MachineStatus.IDLE
    assert state.shipments["SH1"].status == ShipmentStatus.RECEIVED
    assert state.inventory["C1"].on_hand == 25
    assert any(isinstance(event, ev.MachineRepairEvent) for event in emitted)
    assert any(isinstance(event, ev.ShipmentReceivedEvent) for event in emitted)


def test_tick_produces_units_consumes_inventory_and_completes_order() -> None:
    state = production_state()
    simulator = FactorySimulator(state)

    emitted = simulator.tick(1)

    assert state.jobs["J1"].produced == 10
    assert state.orders["O1"].status == OrderStatus.COMPLETE
    assert state.inventory["C1"].on_hand == 10
    assert state.production_cost == 20
    assert any(isinstance(event, ev.OrderCompleteEvent) for event in emitted)


def test_identical_runs_produce_identical_state_and_log() -> None:
    first = FactorySimulator(production_state())
    second = FactorySimulator(production_state())

    first.run_until(2, step=1)
    second.run_until(2, step=1)

    assert first.state.snapshot_hash() == second.state.snapshot_hash()
    assert [event.model_dump() for event in first.log] == [
        event.model_dump() for event in second.log
    ]
