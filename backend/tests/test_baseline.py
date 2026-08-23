from backend.optimizer.baseline import build_baseline_schedule
from backend.optimizer.models import OptimizeRequest, ScheduleStatus
from backend.simulator.engine import FactorySimulator, SimulationContext
from backend.simulator.models import InventoryItem, Machine, Order, Product, Shipment
from backend.simulator.seed import load_factory
from backend.simulator.state import FactoryState


def small_factory() -> FactoryState:
    return FactoryState(
        machines={
            "M1": Machine(
                id="M1",
                name="Line 1",
                capacity_per_hour=10,
                supported_products=["P1"],
                changeover_minutes=30,
            ),
            "M2": Machine(
                id="M2",
                name="Line 2",
                capacity_per_hour=5,
                supported_products=["P1"],
            ),
        },
        products={
            "P1": Product(id="P1", name="Widget", family="widgets", bom={"C1": 1}),
        },
        orders={
            "O1": Order(id="O1", product_id="P1", quantity=10, due_hour=4),
            "O2": Order(id="O2", product_id="P1", quantity=5, due_hour=6),
        },
        inventory={"C1": InventoryItem(component_id="C1", on_hand=15)},
    )


def test_baseline_is_deterministic_and_validated() -> None:
    state = small_factory()

    first = build_baseline_schedule(state)
    second = build_baseline_schedule(state)

    assert first == second
    assert first.status == ScheduleStatus.FEASIBLE
    assert first.is_committable
    assert state.jobs == {}


def test_baseline_waits_for_inventory_shipment() -> None:
    state = small_factory()
    state.inventory["C1"].on_hand = 5
    state.shipments["SH1"] = Shipment(
        id="SH1",
        supplier_id="S1",
        component_id="C1",
        quantity=10,
        eta_hour=3,
    )

    result = build_baseline_schedule(state)

    assert result.validation is not None
    assert result.validation.is_valid
    assert any(job.start_hour == 3 for job in result.jobs)


def test_baseline_explains_orders_it_cannot_schedule() -> None:
    state = small_factory()
    state.orders["O3"] = Order(
        id="O3",
        product_id="P1",
        quantity=100,
        due_hour=10,
    )

    # Wide enough for the small orders once their windows carry the headroom
    # the engine needs, but nowhere near enough for O3.
    result = build_baseline_schedule(
        state,
        OptimizeRequest(horizon_hours=4),
    )

    assert result.status == ScheduleStatus.PARTIAL
    assert {item.order_id for item in result.unscheduled_orders} == {"O3"}
    assert result.unscheduled_orders[0].reason_code == "insufficient_inventory"


def test_baseline_windows_are_executable_by_the_simulator() -> None:
    """A committed window must be long enough for the engine to finish the job.

    The engine builds in whole ticks and treats a job window as half-open, so a
    window sized to exactly changeover plus production time expires with units
    still owing and the order never completes.
    """
    state = load_factory("factory_01")
    # Orders drawn only from on-hand stock, so this exercises window sizing
    # rather than the scheduler's handling of inbound shipments.
    keep = {"ORD-001", "ORD-003", "ORD-005", "ORD-006"}
    state.orders = {key: order for key, order in state.orders.items() if key in keep}
    result = build_baseline_schedule(state)
    assert result.is_committable

    state.schedule_version += 1
    state.jobs = {
        job.id: job.model_copy(update={"schedule_version": state.schedule_version})
        for job in result.jobs
    }
    simulator = FactorySimulator(state, SimulationContext(step_hours=0.25))
    simulator.run_until(max(job.end_hour for job in result.jobs), 0.25)

    unfinished = [job.id for job in state.job_list() if job.produced < job.quantity]
    assert unfinished == []
