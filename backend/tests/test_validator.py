from backend.optimizer.models import ViolationCode
from backend.optimizer.validator import validate_schedule
from backend.simulator.models import (
    InventoryItem,
    Machine,
    MachineStatus,
    Order,
    Product,
    ProductionJob,
    Shipment,
)
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
            "M2": Machine(
                id="M2",
                name="Line 2",
                capacity_per_hour=10,
                supported_products=["P2"],
            ),
        },
        products={
            "P1": Product(
                id="P1",
                name="Product 1",
                family="one",
                bom={"C1": 2},
            ),
            "P2": Product(
                id="P2",
                name="Product 2",
                family="two",
            ),
        },
        orders={
            "O1": Order(
                id="O1",
                product_id="P1",
                quantity=10,
                due_hour=10,
            ),
        },
        inventory={
            "C1": InventoryItem(
                component_id="C1",
                on_hand=20,
            ),
        },
    )


def job(
    job_id: str = "J1",
    order_id: str = "O1",
    machine_id: str = "M1",
    product_id: str = "P1",
    start_hour: float = 0,
    end_hour: float = 1,
    quantity: int = 10,
) -> ProductionJob:
    return ProductionJob(
        id=job_id,
        order_id=order_id,
        machine_id=machine_id,
        product_id=product_id,
        start_hour=start_hour,
        end_hour=end_hour,
        quantity=quantity,
    )


def violation_codes(
    state: FactoryState, jobs: list[ProductionJob]
) -> set[ViolationCode]:
    result = validate_schedule(state, jobs)
    return {violation.code for violation in result.violations}


def test_valid_schedule_passes_without_mutating_state() -> None:
    state = factory_state()
    original_hash = state.snapshot_hash()

    result = validate_schedule(state, [job()])

    assert result.is_valid
    assert state.snapshot_hash() == original_hash


def test_validator_reports_unknown_references() -> None:
    codes = violation_codes(
        factory_state(),
        [
            job(
                order_id="missing-order",
                machine_id="missing-machine",
                product_id="missing-product",
            ),
        ],
    )

    assert ViolationCode.UNKNOWN_ORDER in codes
    assert ViolationCode.UNKNOWN_MACHINE in codes
    assert ViolationCode.UNKNOWN_PRODUCT in codes


def test_validator_reports_product_and_machine_mismatches() -> None:
    codes = violation_codes(
        factory_state(),
        [job(machine_id="M2", product_id="P2")],
    )

    assert ViolationCode.ORDER_PRODUCT_MISMATCH in codes
    assert ViolationCode.INCOMPATIBLE_MACHINE not in codes

    incompatible = violation_codes(
        factory_state(),
        [job(machine_id="M2")],
    )
    assert ViolationCode.INCOMPATIBLE_MACHINE in incompatible


def test_validator_reports_downtime_past_starts_and_overlaps() -> None:
    state = factory_state()
    state.sim_hour = 2
    state.machines["M1"].status = MachineStatus.DOWN
    state.machines["M1"].down_until_hour = 4
    jobs = [
        job(job_id="J1", start_hour=1, end_hour=3, quantity=5),
        job(job_id="J2", start_hour=2, end_hour=4, quantity=5),
    ]

    codes = violation_codes(state, jobs)

    assert ViolationCode.MACHINE_DOWN in codes
    assert ViolationCode.PAST_START in codes
    assert ViolationCode.OVERLAPPING_JOBS in codes


def test_validator_reports_duplicate_ids_and_overproduction() -> None:
    jobs = [
        job(quantity=6),
        job(start_hour=1, end_hour=2, quantity=6),
    ]

    codes = violation_codes(factory_state(), jobs)

    assert ViolationCode.DUPLICATE_JOB in codes
    assert ViolationCode.INVALID_QUANTITY in codes


def test_inventory_requires_stock_available_when_job_starts() -> None:
    state = factory_state()
    state.inventory["C1"].on_hand = 10
    state.shipments["SH1"] = Shipment(
        id="SH1",
        supplier_id="S1",
        component_id="C1",
        quantity=10,
        eta_hour=1,
    )

    before_arrival = violation_codes(state, [job(end_hour=0.5)])
    after_arrival = validate_schedule(
        state,
        [job(start_hour=1, end_hour=2)],
    )

    assert ViolationCode.INSUFFICIENT_INVENTORY in before_arrival
    assert after_arrival.is_valid
