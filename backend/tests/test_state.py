from backend.simulator.models import (
    Machine,
    Order,
    OrderStatus,
    ProductionJob,
)
from backend.simulator.state import FactoryState


def make_machine(machine_id: str) -> Machine:
    return Machine(
        id=machine_id,
        name=f"Machine {machine_id}",
        capacity_per_hour=20,
        supported_products=["P1"],
    )


def make_order(
    order_id: str,
    status: OrderStatus = OrderStatus.PENDING,
) -> Order:
    return Order(
        id=order_id,
        product_id="P1",
        quantity=100,
        due_hour=24,
        status=status,
    )


def make_job(job_id: str, machine_id: str) -> ProductionJob:
    return ProductionJob(
        id=job_id,
        order_id="O1",
        machine_id=machine_id,
        product_id="P1",
        start_hour=0,
        end_hour=5,
        quantity=100,
    )


def test_state_defaults_to_empty_factory() -> None:
    state = FactoryState()

    assert state.name == "factory_01"
    assert state.sim_hour == 0
    assert state.machine_list() == []
    assert state.order_list() == []
    assert state.total_cost() == 0


def test_accessors_return_entities_in_id_order() -> None:
    state = FactoryState(
        machines={
            "M2": make_machine("M2"),
            "M1": make_machine("M1"),
        },
        orders={
            "O2": make_order("O2"),
            "O1": make_order("O1"),
        },
        jobs={
            "J2": make_job("J2", "M1"),
            "J1": make_job("J1", "M1"),
        },
    )

    assert [machine.id for machine in state.machine_list()] == ["M1", "M2"]
    assert [order.id for order in state.order_list()] == ["O1", "O2"]
    assert [job.id for job in state.job_list()] == ["J1", "J2"]


def test_state_filters_open_orders_and_machine_jobs() -> None:
    state = FactoryState(
        orders={
            "O1": make_order("O1"),
            "O2": make_order("O2", OrderStatus.COMPLETE),
        },
        jobs={
            "J1": make_job("J1", "M1"),
            "J2": make_job("J2", "M2"),
        },
    )

    assert [order.id for order in state.open_orders()] == ["O1"]
    assert [job.id for job in state.jobs_for_machine("M1")] == ["J1"]


def test_total_cost_combines_actual_costs() -> None:
    state = FactoryState(
        production_cost=100.1234567,
        late_penalty_cost=20.7654321,
    )

    assert state.total_cost() == 120.888889


def test_snapshot_hash_is_stable_and_tracks_changes() -> None:
    first = FactoryState(
        machines={
            "M1": make_machine("M1"),
            "M2": make_machine("M2"),
        },
    )
    second = FactoryState(
        machines={
            "M2": make_machine("M2"),
            "M1": make_machine("M1"),
        },
    )

    assert first.snapshot_hash() == second.snapshot_hash()

    second.sim_hour = 1

    assert first.snapshot_hash() != second.snapshot_hash()


def test_clone_does_not_share_mutable_entities() -> None:
    original = FactoryState(orders={"O1": make_order("O1")})
    cloned = original.clone()

    cloned.orders["O1"].produced = 40

    assert cloned.orders["O1"].produced == 40
    assert original.orders["O1"].produced == 0
