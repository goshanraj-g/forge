"""Independent validation for candidate production schedules."""

from __future__ import annotations

from collections import Counter, defaultdict
from itertools import pairwise
from math import ceil

from backend.optimizer.models import (
    ScheduleViolation,
    ValidationResult,
    ViolationCode,
)
from backend.simulator.models import (
    MachineStatus,
    ProductionJob,
    ShipmentStatus,
)
from backend.simulator.state import FactoryState


def validate_schedule(
    state: FactoryState,
    jobs: list[ProductionJob],
    hard_deadline_orders: set[str] | None = None,
) -> ValidationResult:
    """Validate a candidate without modifying factory state."""
    violations: list[ScheduleViolation] = []

    _check_duplicate_ids(jobs, violations)
    _check_job_references(state, jobs, violations)
    _check_machine_overlaps(jobs, violations)
    _check_job_durations(state, jobs, violations)
    _check_order_quantities(state, jobs, violations)
    _check_hard_deadlines(
        state,
        jobs,
        hard_deadline_orders or set(),
        violations,
    )
    _check_inventory(state, jobs, violations)

    return ValidationResult(violations=violations)


def _check_duplicate_ids(
    jobs: list[ProductionJob],
    violations: list[ScheduleViolation],
) -> None:
    counts = Counter(job.id for job in jobs)

    for job_id in sorted(counts):
        if counts[job_id] > 1:
            violations.append(
                ScheduleViolation(
                    code=ViolationCode.DUPLICATE_JOB,
                    message=f"job {job_id!r} appears more than once",
                    job_ids=[job_id],
                ),
            )


def _check_job_references(
    state: FactoryState,
    jobs: list[ProductionJob],
    violations: list[ScheduleViolation],
) -> None:
    for job in sorted(jobs, key=lambda item: item.id):
        order = state.orders.get(job.order_id)
        machine = state.machines.get(job.machine_id)
        product = state.products.get(job.product_id)

        if order is None:
            violations.append(
                ScheduleViolation(
                    code=ViolationCode.UNKNOWN_ORDER,
                    message=(
                        f"job {job.id!r} references unknown order {job.order_id!r}"
                    ),
                    job_ids=[job.id],
                    order_ids=[job.order_id],
                ),
            )

        if machine is None:
            violations.append(
                ScheduleViolation(
                    code=ViolationCode.UNKNOWN_MACHINE,
                    message=(
                        f"job {job.id!r} references unknown machine {job.machine_id!r}"
                    ),
                    job_ids=[job.id],
                ),
            )

        if product is None:
            violations.append(
                ScheduleViolation(
                    code=ViolationCode.UNKNOWN_PRODUCT,
                    message=(
                        f"job {job.id!r} references unknown product {job.product_id!r}"
                    ),
                    job_ids=[job.id],
                ),
            )

        if order is not None and order.product_id != job.product_id:
            violations.append(
                ScheduleViolation(
                    code=ViolationCode.ORDER_PRODUCT_MISMATCH,
                    message=(
                        f"job {job.id!r} produces {job.product_id!r} "
                        f"for order {order.id!r}, which requires "
                        f"{order.product_id!r}"
                    ),
                    job_ids=[job.id],
                    order_ids=[order.id],
                ),
            )

        if machine is not None:
            if not machine.can_produce(job.product_id):
                violations.append(
                    ScheduleViolation(
                        code=ViolationCode.INCOMPATIBLE_MACHINE,
                        message=(
                            f"machine {machine.id!r} cannot produce {job.product_id!r}"
                        ),
                        job_ids=[job.id],
                    ),
                )

            unavailable = (
                machine.status == MachineStatus.MAINTENANCE
                or (
                    machine.status == MachineStatus.DOWN
                    and machine.down_until_hour is None
                )
                or (
                    machine.down_until_hour is not None
                    and job.start_hour < machine.down_until_hour
                )
            )

            if unavailable:
                violations.append(
                    ScheduleViolation(
                        code=ViolationCode.MACHINE_DOWN,
                        message=(
                            f"machine {machine.id!r} is unavailable "
                            f"when job {job.id!r} starts"
                        ),
                        job_ids=[job.id],
                    ),
                )

        if job.start_hour < state.sim_hour:
            violations.append(
                ScheduleViolation(
                    code=ViolationCode.PAST_START,
                    message=(
                        f"job {job.id!r} starts at {job.start_hour}, "
                        f"before current time {state.sim_hour}"
                    ),
                    job_ids=[job.id],
                ),
            )

        if job.quantity <= 0:
            violations.append(
                ScheduleViolation(
                    code=ViolationCode.INVALID_QUANTITY,
                    message=(f"job {job.id!r} has nonpositive quantity {job.quantity}"),
                    job_ids=[job.id],
                    order_ids=[job.order_id],
                ),
            )


def _check_machine_overlaps(
    jobs: list[ProductionJob],
    violations: list[ScheduleViolation],
) -> None:
    by_machine: dict[str, list[ProductionJob]] = defaultdict(list)

    for job in jobs:
        by_machine[job.machine_id].append(job)

    for machine_id in sorted(by_machine):
        machine_jobs = sorted(
            by_machine[machine_id],
            key=lambda job: (
                job.start_hour,
                job.end_hour,
                job.id,
            ),
        )

        for previous, current in pairwise(machine_jobs):
            if current.start_hour < previous.end_hour:
                violations.append(
                    ScheduleViolation(
                        code=ViolationCode.OVERLAPPING_JOBS,
                        message=(
                            f"jobs {previous.id!r} and {current.id!r} "
                            f"overlap on machine {machine_id!r}"
                        ),
                        job_ids=[previous.id, current.id],
                    ),
                )


def _check_order_quantities(
    state: FactoryState,
    jobs: list[ProductionJob],
    violations: list[ScheduleViolation],
) -> None:
    scheduled: dict[str, int] = defaultdict(int)

    for job in jobs:
        scheduled[job.order_id] += job.quantity

    for order_id in sorted(scheduled):
        order = state.orders.get(order_id)

        if order is None:
            continue

        # Job quantities are whole units, so covering a fractional remainder
        # requires rounding up. Anything beyond that is real over-production.
        if scheduled[order_id] > ceil(order.remaining):
            violations.append(
                ScheduleViolation(
                    code=ViolationCode.INVALID_QUANTITY,
                    message=(
                        f"order {order_id!r} has {scheduled[order_id]} "
                        f"scheduled units but only {order.remaining} "
                        "units remain"
                    ),
                    job_ids=[job.id for job in jobs if job.order_id == order_id],
                    order_ids=[order_id],
                ),
            )


def _check_job_durations(
    state: FactoryState,
    jobs: list[ProductionJob],
    violations: list[ScheduleViolation],
) -> None:
    by_machine: dict[str, list[ProductionJob]] = defaultdict(list)
    for job in jobs:
        by_machine[job.machine_id].append(job)

    for machine_id in sorted(by_machine):
        machine = state.machines.get(machine_id)
        if machine is None:
            continue

        family = machine.current_family
        for job in sorted(
            by_machine[machine_id],
            key=lambda item: (item.start_hour, item.id),
        ):
            product = state.products.get(job.product_id)
            if product is None:
                continue

            production_hours = (
                job.quantity / machine.capacity_per_hour
                if machine.capacity_per_hour > 0
                else float("inf")
            )
            changeover_hours = (
                machine.changeover_minutes / 60 if family != product.family else 0.0
            )
            required = production_hours + changeover_hours
            scheduled = job.end_hour - job.start_hour
            if scheduled + 1e-6 < required:
                violations.append(
                    ScheduleViolation(
                        code=ViolationCode.INSUFFICIENT_DURATION,
                        message=(
                            f"job {job.id!r} reserves {scheduled} hours "
                            f"but requires at least {required} hours"
                        ),
                        job_ids=[job.id],
                        order_ids=[job.order_id],
                    ),
                )
            family = product.family


def _check_hard_deadlines(
    state: FactoryState,
    jobs: list[ProductionJob],
    hard_deadline_orders: set[str],
    violations: list[ScheduleViolation],
) -> None:
    jobs_by_order: dict[str, list[ProductionJob]] = defaultdict(list)
    for job in jobs:
        jobs_by_order[job.order_id].append(job)

    for order_id in sorted(hard_deadline_orders):
        order = state.orders.get(order_id)
        if order is None:
            continue
        order_jobs = jobs_by_order[order_id]
        if order_jobs and max(job.end_hour for job in order_jobs) > order.due_hour:
            violations.append(
                ScheduleViolation(
                    code=ViolationCode.MISSED_HARD_DEADLINE,
                    message=(
                        f"order {order_id!r} finishes after its hard "
                        f"deadline at hour {order.due_hour}"
                    ),
                    job_ids=[job.id for job in order_jobs],
                    order_ids=[order_id],
                ),
            )


def _check_inventory(
    state: FactoryState,
    jobs: list[ProductionJob],
    violations: list[ScheduleViolation],
) -> None:
    available = {
        component_id: item.available for component_id, item in state.inventory.items()
    }
    received_shipments: set[str] = set()

    ordered_jobs = sorted(
        jobs,
        key=lambda job: (
            job.start_hour,
            job.machine_id,
            job.id,
        ),
    )

    for job in ordered_jobs:
        for shipment in state.shipment_list():
            if shipment.id in received_shipments:
                continue

            if shipment.status == ShipmentStatus.RECEIVED:
                continue

            if shipment.eta_hour <= job.start_hour:
                available[shipment.component_id] = (
                    available.get(shipment.component_id, 0) + shipment.quantity
                )
                received_shipments.add(shipment.id)

        product = state.products.get(job.product_id)

        if product is None:
            continue

        for component_id in sorted(product.bom):
            required = product.bom[component_id] * job.quantity
            on_hand = available.get(component_id, 0)

            if required > on_hand:
                # One violation per job/component is enough; avoid cascading negatives.
                violations.append(
                    ScheduleViolation(
                        code=ViolationCode.INSUFFICIENT_INVENTORY,
                        message=(
                            f"job {job.id!r} requires {required} "
                            f"units of {component_id!r}, but only "
                            f"{on_hand} are available at its start"
                        ),
                        job_ids=[job.id],
                        order_ids=[job.order_id],
                    ),
                )
                available[component_id] = 0
            else:
                available[component_id] = on_hand - required
