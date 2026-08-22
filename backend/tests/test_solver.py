from backend.optimizer.models import (
    OptimizeRequest,
    ScheduleStatus,
    UnscheduledReason,
)
from backend.optimizer.solver import optimize_schedule
from backend.simulator.models import (
    InventoryItem,
    Machine,
    MachineStatus,
    Order,
    Product,
    Shipment,
)
from backend.simulator.seed import factory_01
from backend.simulator.state import FactoryState


def factory_state() -> FactoryState:
    return FactoryState(
        machines={
            "M1": Machine(
                id="M1",
                name="Line 1",
                capacity_per_hour=10,
                supported_products=["P1"],
            ),
        },
        products={
            "P1": Product(id="P1", name="Widget", family="widget"),
        },
        orders={
            "O1": Order(
                id="O1",
                product_id="P1",
                quantity=10,
                due_hour=1,
                late_penalty_per_hour=100,
            ),
            "O2": Order(
                id="O2",
                product_id="P1",
                quantity=10,
                due_hour=3,
                late_penalty_per_hour=100,
            ),
        },
    )


def test_solver_finds_valid_schedule_with_urgent_order_first() -> None:
    result = optimize_schedule(factory_state())

    assert result.status == ScheduleStatus.OPTIMAL
    assert result.is_committable
    assert [
        job.order_id for job in sorted(result.jobs, key=lambda job: job.start_hour)
    ] == [
        "O1",
        "O2",
    ]
    assert result.cost.late_penalty == 0


def test_solver_waits_for_temporarily_down_machine() -> None:
    state = factory_state()
    state.orders = {"O1": state.orders["O1"]}
    state.machines["M1"].status = MachineStatus.DOWN
    state.machines["M1"].down_until_hour = 3

    result = optimize_schedule(state)

    assert result.status == ScheduleStatus.OPTIMAL
    assert result.jobs[0].start_hour == 3


def test_solver_reports_missing_product_information() -> None:
    state = factory_state()
    state.products = {}

    result = optimize_schedule(
        state,
        OptimizeRequest(time_limit_seconds=1),
    )

    assert result.status == ScheduleStatus.NEEDS_INFORMATION
    assert {item.reason_code for item in result.unscheduled_orders} == {
        "unknown_product",
    }


def test_solver_waits_for_inventory_shipment() -> None:
    state = factory_state()
    state.orders = {"O1": state.orders["O1"]}
    state.products["P1"].bom = {"C1": 1}
    state.inventory["C1"] = InventoryItem(component_id="C1", on_hand=0)
    state.shipments["SH1"] = Shipment(
        id="SH1",
        supplier_id="S1",
        component_id="C1",
        quantity=10,
        eta_hour=3,
    )

    result = optimize_schedule(state)

    assert result.status == ScheduleStatus.OPTIMAL
    assert result.jobs[0].start_hour == 3
    assert result.validation is not None
    assert result.validation.is_valid


def test_solver_minimizes_family_changeovers() -> None:
    state = factory_state()
    state.machines["M1"].changeover_minutes = 60
    state.machines["M1"].current_family = "family-a"
    state.products["P1"].family = "family-a"
    state.products["P2"] = Product(
        id="P2",
        name="Other widget",
        family="family-b",
    )
    state.machines["M1"].supported_products.append("P2")
    state.orders = {
        "O1": Order(id="O1", product_id="P1", quantity=10, due_hour=20),
        "O2": Order(id="O2", product_id="P2", quantity=10, due_hour=20),
    }

    result = optimize_schedule(state)
    ordered = sorted(result.jobs, key=lambda job: job.start_hour)

    assert result.status == ScheduleStatus.OPTIMAL
    assert [job.order_id for job in ordered] == ["O1", "O2"]
    assert ordered[0].end_hour <= ordered[1].start_hour
    assert result.cost.changeover == 80


def test_solver_proves_impossible_hard_deadline() -> None:
    state = factory_state()
    state.orders = {
        "O1": Order(
            id="O1",
            product_id="P1",
            quantity=20,
            due_hour=1,
        ),
    }

    result = optimize_schedule(
        state,
        OptimizeRequest(
            horizon_hours=4,
            hard_deadline_orders=["O1"],
        ),
    )

    assert result.status == ScheduleStatus.INFEASIBLE
    assert result.unscheduled_orders[0].reason_code == UnscheduledReason.HARD_DEADLINE


def test_seed_factory_produces_valid_candidate() -> None:
    result = optimize_schedule(
        factory_01(),
        OptimizeRequest(time_limit_seconds=10),
    )

    assert result.status in {
        ScheduleStatus.OPTIMAL,
        ScheduleStatus.FEASIBLE,
    }
    assert result.validation is not None
    assert result.validation.is_valid
    assert len(result.jobs) == 12


def test_solver_returns_partial_schedule_when_one_order_lacks_inventory() -> None:
    state = factory_state()
    state.products["P1"].bom = {"C1": 1}
    state.products["P2"] = Product(
        id="P2",
        name="Inventory-free widget",
        family="widget",
    )
    state.machines["M1"].supported_products.append("P2")
    state.orders["O2"].product_id = "P2"

    result = optimize_schedule(state)

    assert result.status == ScheduleStatus.PARTIAL
    assert {job.order_id for job in result.jobs} == {"O2"}
    assert result.unscheduled_orders[0].order_id == "O1"
    assert (
        result.unscheduled_orders[0].reason_code
        == UnscheduledReason.INSUFFICIENT_INVENTORY
    )
    assert result.validation is not None
    assert result.validation.is_valid
