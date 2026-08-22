"""Constraint-based production scheduling using OR-Tools CP-SAT."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from time import perf_counter

from ortools.sat.python import cp_model

from backend.optimizer.models import (
    OptimizeRequest,
    ScheduleCost,
    ScheduleResult,
    ScheduleStatus,
    UnscheduledOrder,
)
from backend.optimizer.validator import validate_schedule
from backend.simulator.engine import (
    CHANGEOVER_COST_PER_HOUR,
    OVERTIME_COST_PER_HOUR,
    overtime_overlap,
)
from backend.simulator.models import (
    Machine,
    MachineStatus,
    Order,
    Product,
    ProductionJob,
    ShipmentStatus,
    q,
)
from backend.simulator.state import FactoryState


@dataclass
class _JobVariables:
    order: Order
    product: Product
    starts: dict[str, cp_model.IntVar]
    ends: dict[str, cp_model.IntVar]
    assigned: dict[str, cp_model.IntVar]
    intervals: dict[str, cp_model.IntervalVar]
    start_time: cp_model.IntVar
    completion: cp_model.IntVar
    lateness: cp_model.IntVar


def _to_bucket(
    hour: float,
    start_hour: float,
    bucket_hours: float,
) -> int:
    """Convert an absolute hour into a relative planning bucket."""
    return max(0, ceil((hour - start_hour) / bucket_hours))


def _duration_buckets(
    order: Order,
    machine: Machine,
    bucket_hours: float,
) -> int:
    """Return the whole number of buckets required to produce an order."""
    production_hours = order.remaining / machine.capacity_per_hour
    return max(1, ceil(production_hours / bucket_hours))


def _compatible_machines(
    state: FactoryState,
    product: Product,
) -> list[Machine]:
    """Return usable machines capable of producing a product."""
    return [
        machine
        for machine in state.machine_list()
        if machine.can_produce(product.id)
        and machine.capacity_per_hour > 0
        and machine.status != MachineStatus.MAINTENANCE
        and not (
            machine.status == MachineStatus.DOWN and machine.down_until_hour is None
        )
    ]


def optimize_schedule(
    state: FactoryState,
    request: OptimizeRequest | None = None,
) -> ScheduleResult:
    """Build and solve a production scheduling constraint model."""
    options = request or OptimizeRequest()
    model = cp_model.CpModel()

    horizon_buckets = ceil(
        options.horizon_hours / options.bucket_hours,
    )

    job_variables: list[_JobVariables] = []
    unscheduled: list[UnscheduledOrder] = []
    missing_information: list[UnscheduledOrder] = []
    objective_terms: list[cp_model.LinearExpr] = []

    machine_intervals: dict[str, list[cp_model.IntervalVar]] = {
        machine.id: [] for machine in state.machine_list()
    }

    orders = sorted(
        state.open_orders(),
        key=lambda order: (
            order.priority,
            order.due_hour,
            order.id,
        ),
    )

    for order in orders:
        product = state.products.get(order.product_id)

        if product is None:
            missing_information.append(
                _unscheduled(
                    order,
                    "unknown_product",
                    "The order references a product that does not exist.",
                ),
            )
            continue

        machines = _compatible_machines(state, product)

        starts: dict[str, cp_model.IntVar] = {}
        ends: dict[str, cp_model.IntVar] = {}
        assigned: dict[str, cp_model.IntVar] = {}
        intervals: dict[str, cp_model.IntervalVar] = {}

        for machine in machines:
            duration = _duration_buckets(
                order,
                machine,
                options.bucket_hours,
            )

            if duration > horizon_buckets:
                continue

            machine_id = machine.id
            variable_name = f"{order.id}_{machine_id}"
            earliest_start = _to_bucket(
                machine.down_until_hour or state.sim_hour,
                state.sim_hour,
                options.bucket_hours,
            )

            if earliest_start + duration > horizon_buckets:
                continue

            start = model.new_int_var(
                earliest_start,
                horizon_buckets - duration,
                f"start_{variable_name}",
            )

            end = model.new_int_var(
                duration,
                horizon_buckets,
                f"end_{variable_name}",
            )

            is_assigned = model.new_bool_var(
                f"assigned_{variable_name}",
            )

            interval = model.new_optional_interval_var(
                start,
                duration,
                end,
                is_assigned,
                f"interval_{variable_name}",
            )

            starts[machine_id] = start
            ends[machine_id] = end
            assigned[machine_id] = is_assigned
            intervals[machine_id] = interval

            machine_intervals[machine_id].append(interval)
            _add_overtime_term(
                model,
                state,
                options,
                start,
                is_assigned,
                duration,
                earliest_start,
                horizon_buckets,
                objective_terms,
            )

        if not assigned:
            unscheduled.append(
                _unscheduled(
                    order,
                    "no_machine_capacity",
                    "No compatible machine can finish the order in the horizon.",
                ),
            )
            continue

        model.add_exactly_one(list(assigned.values()))

        start_time = model.new_int_var(
            0,
            horizon_buckets,
            f"selected_start_{order.id}",
        )
        completion = model.new_int_var(
            0,
            horizon_buckets,
            f"completion_{order.id}",
        )
        for machine_id, is_assigned in assigned.items():
            model.add(start_time == starts[machine_id]).only_enforce_if(is_assigned)
            model.add(completion == ends[machine_id]).only_enforce_if(is_assigned)

        due_bucket = _to_bucket(
            order.due_hour,
            state.sim_hour,
            options.bucket_hours,
        )
        lateness = model.new_int_var(
            0,
            horizon_buckets,
            f"lateness_{order.id}",
        )
        model.add_max_equality(lateness, [completion - due_bucket, 0])
        if order.id in options.hard_deadline_orders:
            model.add(completion <= due_bucket)

        penalty_weight = max(
            1,
            round(
                order.late_penalty_per_hour
                * options.weights.late_delivery
                * options.bucket_hours
                * 100,
            ),
        )
        objective_terms.append(lateness * penalty_weight)

        job_variables.append(
            _JobVariables(
                order=order,
                product=product,
                starts=starts,
                ends=ends,
                assigned=assigned,
                intervals=intervals,
                start_time=start_time,
                completion=completion,
                lateness=lateness,
            ),
        )

    for machine_jobs in machine_intervals.values():
        if machine_jobs:
            model.add_no_overlap(machine_jobs)

    _add_machine_sequences(
        model,
        state,
        options,
        job_variables,
        objective_terms,
    )

    _add_inventory_constraints(
        model,
        state,
        options,
        horizon_buckets,
        job_variables,
    )

    if missing_information:
        return ScheduleResult(
            status=ScheduleStatus.NEEDS_INFORMATION,
            unscheduled_orders=[*missing_information, *unscheduled],
            notes=["Missing product data must be corrected before scheduling."],
        )

    model.minimize(sum(objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = options.time_limit_seconds
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0

    started = perf_counter()
    solver_status = solver.solve(model)
    solve_seconds = perf_counter() - started

    if solver_status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        status = (
            ScheduleStatus.INFEASIBLE
            if solver_status == cp_model.INFEASIBLE
            else ScheduleStatus.UNKNOWN
        )
        blocked_orders = [
            _unscheduled(
                item.order,
                "constraint_conflict"
                if status == ScheduleStatus.INFEASIBLE
                else "search_incomplete",
                "The complete constraint model has no feasible schedule."
                if status == ScheduleStatus.INFEASIBLE
                else "Search ended before a feasible schedule was established.",
            )
            for item in job_variables
        ]
        return ScheduleResult(
            status=status,
            unscheduled_orders=[*unscheduled, *blocked_orders],
            solve_seconds=solve_seconds,
            time_limit_seconds=options.time_limit_seconds,
            notes=[f"CP-SAT finished with status {solver.status_name(solver_status)}."],
        )

    jobs = _read_jobs(state, options, solver, job_variables)
    validation = validate_schedule(
        state,
        jobs,
        set(options.hard_deadline_orders),
    )
    status = (
        ScheduleStatus.INFEASIBLE
        if unscheduled and not jobs
        else ScheduleStatus.PARTIAL
        if unscheduled
        else (
            ScheduleStatus.OPTIMAL
            if solver_status == cp_model.OPTIMAL
            else ScheduleStatus.FEASIBLE
        )
    )
    if not validation.is_valid:
        status = ScheduleStatus.ERROR

    late_penalty = sum(
        max(0.0, job.end_hour - state.orders[job.order_id].due_hour)
        * state.orders[job.order_id].late_penalty_per_hour
        for job in jobs
    )
    overtime_hours = sum(overtime_overlap(job.start_hour, job.end_hour) for job in jobs)
    changeover_hours = _scheduled_changeover_hours(state, jobs)
    objective_value = solver.objective_value
    objective_bound = solver.best_objective_bound
    optimality_gap = (
        0.0
        if solver_status == cp_model.OPTIMAL
        else abs(objective_value - objective_bound) / max(abs(objective_value), 1.0)
    )
    return ScheduleResult(
        status=status,
        jobs=jobs,
        unscheduled_orders=unscheduled,
        cost=ScheduleCost(
            late_penalty=q(late_penalty),
            overtime=q(overtime_hours * OVERTIME_COST_PER_HOUR),
            changeover=q(changeover_hours * CHANGEOVER_COST_PER_HOUR),
        ),
        optimality_gap=q(optimality_gap),
        solve_seconds=solve_seconds,
        time_limit_seconds=options.time_limit_seconds,
        validation=validation,
        notes=[f"CP-SAT finished with status {solver.status_name(solver_status)}."],
    )


def _read_jobs(
    state: FactoryState,
    options: OptimizeRequest,
    solver: cp_model.CpSolver,
    variables: list[_JobVariables],
) -> list[ProductionJob]:
    schedule_version = state.schedule_version + 1
    selected: list[tuple[float, float, str, _JobVariables]] = []

    for item in variables:
        for machine_id in sorted(item.assigned):
            if not solver.boolean_value(item.assigned[machine_id]):
                continue

            selected.append(
                (
                    solver.value(item.starts[machine_id]),
                    solver.value(item.ends[machine_id]),
                    machine_id,
                    item,
                ),
            )
            break

    jobs: list[ProductionJob] = []
    family_by_machine = {
        machine.id: machine.current_family for machine in state.machine_list()
    }
    for start_bucket, end_bucket, machine_id, item in sorted(
        selected,
        key=lambda row: (row[0], row[2], row[3].order.id),
    ):
        machine = state.machines[machine_id]
        previous_family = family_by_machine[machine_id]
        changeover = (
            machine.changeover_minutes / 60
            if previous_family != item.product.family
            else 0.0
        )
        production_start = state.sim_hour + start_bucket * options.bucket_hours
        jobs.append(
            ProductionJob(
                id=f"job-{schedule_version}-{len(jobs) + 1:04d}",
                order_id=item.order.id,
                machine_id=machine_id,
                product_id=item.product.id,
                start_hour=q(production_start - changeover),
                end_hour=q(
                    state.sim_hour + end_bucket * options.bucket_hours,
                ),
                quantity=int(item.order.remaining),
                schedule_version=schedule_version,
            ),
        )
        family_by_machine[machine_id] = item.product.family

    return jobs


def _add_machine_sequences(
    model: cp_model.CpModel,
    state: FactoryState,
    options: OptimizeRequest,
    variables: list[_JobVariables],
    objective_terms: list[cp_model.LinearExpr],
) -> None:
    for machine in state.machine_list():
        items = [item for item in variables if machine.id in item.assigned]
        if not items:
            continue

        arcs: list[tuple[int, int, cp_model.LiteralT]] = []
        assignments = [item.assigned[machine.id] for item in items]
        machine_empty = model.new_bool_var(f"{machine.id}_empty")
        arcs.append((0, 0, machine_empty))
        model.add(sum(assignments) == 0).only_enforce_if(machine_empty)
        model.add(sum(assignments) >= 1).only_enforce_if(machine_empty.negated())

        for index, item in enumerate(items, start=1):
            selected = item.assigned[machine.id]
            arcs.append((index, index, selected.negated()))

            first = model.new_bool_var(f"{machine.id}_first_{item.order.id}")
            last = model.new_bool_var(f"{machine.id}_last_{item.order.id}")
            arcs.extend(((0, index, first), (index, 0, last)))

            setup = _changeover_buckets(
                machine,
                machine.current_family,
                item.product.family,
                options.bucket_hours,
            )
            available = _to_bucket(
                machine.down_until_hour or state.sim_hour,
                state.sim_hour,
                options.bucket_hours,
            )
            model.add(
                item.starts[machine.id] >= available + setup,
            ).only_enforce_if(first)
            _append_changeover_term(
                first,
                setup,
                options,
                objective_terms,
            )

        for before_index, before in enumerate(items, start=1):
            for after_index, after in enumerate(items, start=1):
                if before_index == after_index:
                    continue

                follows = model.new_bool_var(
                    f"{machine.id}_{before.order.id}_before_{after.order.id}",
                )
                arcs.append((before_index, after_index, follows))
                setup = _changeover_buckets(
                    machine,
                    before.product.family,
                    after.product.family,
                    options.bucket_hours,
                )
                model.add(
                    after.starts[machine.id] >= before.ends[machine.id] + setup,
                ).only_enforce_if(follows)
                _append_changeover_term(
                    follows,
                    setup,
                    options,
                    objective_terms,
                )

        model.add_circuit(arcs)


def _changeover_buckets(
    machine: Machine,
    previous_family: str | None,
    next_family: str,
    bucket_hours: float,
) -> int:
    if previous_family == next_family:
        return 0
    return ceil((machine.changeover_minutes / 60) / bucket_hours)


def _append_changeover_term(
    transition: cp_model.IntVar,
    buckets: int,
    options: OptimizeRequest,
    objective_terms: list[cp_model.LinearExpr],
) -> None:
    if buckets == 0:
        return
    coefficient = max(
        1,
        round(
            buckets
            * options.bucket_hours
            * CHANGEOVER_COST_PER_HOUR
            * options.weights.changeover
            * 100,
        ),
    )
    objective_terms.append(transition * coefficient)


def _add_overtime_term(
    model: cp_model.CpModel,
    state: FactoryState,
    options: OptimizeRequest,
    start: cp_model.IntVar,
    assigned: cp_model.IntVar,
    duration: int,
    earliest_start: int,
    horizon_buckets: int,
    objective_terms: list[cp_model.LinearExpr],
) -> None:
    overtime = model.new_int_var(
        0,
        duration,
        f"overtime_{start.name}",
    )
    choices = []
    for start_bucket in range(
        earliest_start,
        horizon_buckets - duration + 1,
    ):
        start_hour = state.sim_hour + start_bucket * options.bucket_hours
        end_hour = start_hour + duration * options.bucket_hours
        overtime_buckets = ceil(
            overtime_overlap(start_hour, end_hour) / options.bucket_hours,
        )
        choices.append((start_bucket, overtime_buckets))

    model.add_allowed_assignments([start, overtime], choices).only_enforce_if(
        assigned,
    )
    model.add(overtime == 0).only_enforce_if(assigned.negated())
    coefficient = max(
        1,
        round(
            options.bucket_hours
            * OVERTIME_COST_PER_HOUR
            * options.weights.overtime
            * 100,
        ),
    )
    objective_terms.append(overtime * coefficient)


def _scheduled_changeover_hours(
    state: FactoryState,
    jobs: list[ProductionJob],
) -> float:
    total = 0.0
    for machine in state.machine_list():
        family = machine.current_family
        machine_jobs = sorted(
            (job for job in jobs if job.machine_id == machine.id),
            key=lambda job: (job.start_hour, job.id),
        )
        for job in machine_jobs:
            product_family = state.products[job.product_id].family
            if family != product_family:
                total += machine.changeover_minutes / 60
            family = product_family
    return q(total)


def _add_inventory_constraints(
    model: cp_model.CpModel,
    state: FactoryState,
    options: OptimizeRequest,
    horizon_buckets: int,
    variables: list[_JobVariables],
) -> None:
    scale = 1000
    horizon_end = state.sim_hour + options.horizon_hours
    components = sorted(
        {component_id for item in variables for component_id in item.product.bom},
    )

    for component_id in components:
        requirements = {
            item.order.id: round(
                item.product.bom.get(component_id, 0) * item.order.remaining * scale,
            )
            for item in variables
        }
        initial = round(
            state.inventory[component_id].available * scale
            if component_id in state.inventory
            else 0,
        )
        shipments = [
            shipment
            for shipment in state.shipment_list()
            if shipment.component_id == component_id
            and shipment.status != ShipmentStatus.RECEIVED
            and shipment.eta_hour <= horizon_end
        ]

        total_supply = initial + sum(
            round(shipment.quantity * scale) for shipment in shipments
        )
        model.add(sum(requirements.values()) <= total_supply)

        arrival_buckets = sorted(
            {
                _to_bucket(
                    shipment.eta_hour,
                    state.sim_hour,
                    options.bucket_hours,
                )
                for shipment in shipments
            },
        )
        for arrival_bucket in arrival_buckets:
            if arrival_bucket <= 0 or arrival_bucket > horizon_buckets:
                continue

            consumed_before: list[cp_model.LinearExpr] = []
            for item in variables:
                required = requirements[item.order.id]
                if required == 0:
                    continue

                starts_before = model.new_bool_var(
                    f"{item.order.id}_{component_id}_before_{arrival_bucket}",
                )
                model.add(item.start_time < arrival_bucket).only_enforce_if(
                    starts_before,
                )
                model.add(item.start_time >= arrival_bucket).only_enforce_if(
                    starts_before.negated(),
                )
                consumed_before.append(required * starts_before)

            supply_before = initial + sum(
                round(shipment.quantity * scale)
                for shipment in shipments
                if _to_bucket(
                    shipment.eta_hour,
                    state.sim_hour,
                    options.bucket_hours,
                )
                < arrival_bucket
            )
            model.add(sum(consumed_before) <= supply_before)


def _unscheduled(
    order: Order,
    reason_code: str,
    explanation: str,
) -> UnscheduledOrder:
    return UnscheduledOrder(
        order_id=order.id,
        reason_code=reason_code,
        explanation=explanation,
        required_action="Correct the input data or revise the planning limits.",
    )
