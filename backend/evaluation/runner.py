"""Isolated execution and measurement of factory decision policies."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from backend.evaluation.models import (
    EvaluationDecisionTrace,
    EvaluationMetrics,
    EvaluationResult,
    EvaluationScenario,
)
from backend.evaluation.policies import (
    BASELINE_POLICIES,
    AgentPolicy,
    EvaluationPolicy,
    Investigator,
)
from backend.evaluation.scenarios import scenario_hash
from backend.optimizer.baseline import build_baseline_schedule
from backend.optimizer.models import OptimizeRequest, ScheduleResult
from backend.optimizer.solver import optimize_schedule
from backend.simulator.engine import FactorySimulator, SimulationContext
from backend.simulator.models import OrderStatus, ProductionJob, q
from backend.simulator.seed import load_factory
from backend.simulator.state import FactoryState

Scheduler = Callable[[FactoryState, OptimizeRequest | None], ScheduleResult]


def evaluation_scheduler(
    state: FactoryState,
    request: OptimizeRequest | None = None,
) -> ScheduleResult:
    """Run production CP-SAT with an evaluation-grade solve budget."""
    options = request or OptimizeRequest(time_limit_seconds=60)
    return optimize_schedule(state, options)


def _commit(state: FactoryState, jobs: list[ProductionJob]) -> None:
    state.schedule_version += 1
    committed_jobs = [
        job.model_copy(update={"schedule_version": state.schedule_version})
        for job in jobs
    ]
    state.jobs = {job.id: job for job in committed_jobs}


def _schedule(state: FactoryState, scheduler: Scheduler) -> tuple[bool, int]:
    result = scheduler(state, None)
    violations = (
        len(result.validation.violations) if result.validation is not None else 0
    )
    if not result.is_committable:
        return False, violations
    _commit(state, result.jobs)
    return True, violations


def _prepare_state(scenario: EvaluationScenario) -> FactoryState:
    state = load_factory(scenario.factory_name)
    if scenario.order_ids:
        unknown = set(scenario.order_ids) - set(state.orders)
        if unknown:
            raise ValueError(f"scenario references unknown orders: {sorted(unknown)}")
        state.orders = {
            order_id: state.orders[order_id] for order_id in scenario.order_ids
        }
    return state


def _metrics(
    state: FactoryState,
    *,
    violations: int,
    replans: int,
    policy: EvaluationPolicy,
) -> EvaluationMetrics:
    late_orders = 0
    weighted_lateness = 0.0
    unmet_demand = 0.0
    for order in state.order_list():
        completion_hour = order.completed_hour or state.sim_hour
        lateness = max(0.0, completion_hour - order.due_hour)
        if order.status == OrderStatus.LATE or lateness > 0:
            late_orders += 1
        weighted_lateness += lateness * order.priority
        unmet_demand += order.remaining

    return EvaluationMetrics(
        late_orders=late_orders,
        priority_weighted_lateness=q(weighted_lateness),
        unmet_demand_units=q(unmet_demand),
        penalty_cost=state.late_penalty_cost,
        overtime_cost=state.overtime_cost,
        changeover_cost=state.changeover_cost,
        controllable_cost=state.controllable_cost(),
        production_cost=state.production_cost,
        total_cost=state.total_cost(),
        overtime_hours=state.overtime_hours,
        changeover_hours=state.changeover_hours,
        constraint_violations=violations,
        replans=replans,
        model_calls=policy.model_calls,
        model_cost=policy.model_cost,
    )


def run_scenario(
    scenario: EvaluationScenario,
    policy: EvaluationPolicy,
    *,
    scheduler: Scheduler = build_baseline_schedule,
    initial_schedule: ScheduleResult | None = None,
) -> EvaluationResult:
    """Run one policy from a clean named state and return reproducible metrics."""
    state = _prepare_state(scenario)
    initial_hash = state.snapshot_hash()
    simulator = FactorySimulator(
        state, SimulationContext(step_hours=scenario.step_hours)
    )
    violations = 0
    replans = 0
    decision_event_ids: list[str] = []
    schedule_versions: list[int] = []
    decisions: list[EvaluationDecisionTrace] = []

    if initial_schedule is None:
        committed, schedule_violations = _schedule(state, scheduler)
    else:
        schedule_violations = (
            len(initial_schedule.validation.violations)
            if initial_schedule.validation is not None
            else 0
        )
        committed = initial_schedule.is_committable
        if committed:
            _commit(state, initial_schedule.jobs)
    violations += schedule_violations
    if committed:
        schedule_versions.append(state.schedule_version)

    for source_event in scenario.events:
        event = source_event.model_copy(deep=True)
        simulator.schedule(event)
        simulator.run_until(event.sim_hour, scenario.step_hours)

        state_hash = state.snapshot_hash()
        should_replan = policy.should_replan(
            state.clone(),
            event.model_copy(deep=True),
            scenario,
        )
        committed = False
        if should_replan:
            decision_event_ids.append(event.id)
            replans += 1
            committed, schedule_violations = _schedule(state, scheduler)
            violations += schedule_violations
            if committed:
                schedule_versions.append(state.schedule_version)
        decisions.append(
            EvaluationDecisionTrace(
                event_id=event.id,
                event_type=str(event.type),
                simulation_hour=state.sim_hour,
                state_snapshot_hash=state_hash,
                replan_requested=should_replan,
                schedule_committed=committed,
                resulting_schedule_version=state.schedule_version,
            )
        )

    simulator.run_until(scenario.horizon_hour, scenario.step_hours)
    simulator.finalize()

    return EvaluationResult(
        scenario_id=scenario.id,
        policy_name=policy.name,
        scenario_hash=scenario_hash(scenario),
        initial_state_hash=initial_hash,
        final_state_hash=state.snapshot_hash(),
        metrics=_metrics(
            state,
            violations=violations,
            replans=replans,
            policy=policy,
        ),
        decision_event_ids=decision_event_ids,
        schedule_versions=schedule_versions,
        decisions=decisions,
    )


def compare_baselines(
    scenarios: Iterable[EvaluationScenario],
) -> list[EvaluationResult]:
    """Compare fixed decision policies using the production CP-SAT scheduler."""
    results: list[EvaluationResult] = []
    for scenario in scenarios:
        initial_schedule = _initial_cp_sat_schedule(scenario)
        results.extend(
            run_scenario(
                scenario,
                policy,
                scheduler=evaluation_scheduler,
                initial_schedule=initial_schedule,
            )
            for policy in BASELINE_POLICIES
        )
    return results


def compare_with_agent(
    scenarios: Iterable[EvaluationScenario],
    investigator: Investigator,
) -> list[EvaluationResult]:
    """Add the real agent decision policy to the CP-SAT comparison."""
    scenario_list = list(scenarios)
    results: list[EvaluationResult] = []
    for scenario in scenario_list:
        initial_schedule = _initial_cp_sat_schedule(scenario)
        policies = (*BASELINE_POLICIES, AgentPolicy(investigator))
        results.extend(
            run_scenario(
                scenario,
                policy,
                scheduler=evaluation_scheduler,
                initial_schedule=initial_schedule,
            )
            for policy in policies
        )
    return results


def _initial_cp_sat_schedule(scenario: EvaluationScenario) -> ScheduleResult:
    """Solve once so every policy starts from the identical production plan."""
    # Evaluation favors a trustworthy comparison over API latency. The normal
    # interactive solver limit is intentionally shorter and can expire under CI
    # contention before finding the first feasible plan.
    result = evaluation_scheduler(_prepare_state(scenario))
    if not result.is_committable:
        raise RuntimeError(
            f"CP-SAT could not produce an initial schedule for {scenario.id!r}: "
            f"{result.status}"
        )
    return result
