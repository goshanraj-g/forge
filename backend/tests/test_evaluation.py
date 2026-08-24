from collections import defaultdict
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.agent.models import (
    AgentDecision,
    AgentDecisionRecord,
    DecisionSeverity,
    DecisionStatus,
)
from backend.evaluation import __main__ as evaluation_cli
from backend.evaluation import runner
from backend.evaluation.models import EvaluationScenario
from backend.evaluation.policies import (
    AgentPolicy,
    AlwaysReplanPolicy,
    NoOpPolicy,
    OraclePolicy,
)
from backend.evaluation.runner import (
    compare_baselines,
    compare_with_agent,
    run_scenario,
)
from backend.evaluation.scenarios import load_scenario, load_scenarios, scenario_hash
from backend.optimizer.models import (
    OptimizeRequest,
    ScheduleResult,
    ScheduleStatus,
    ValidationResult,
)
from backend.simulator.events import BaseEvent, MachineFailureEvent
from backend.simulator.state import FactoryState


def _scenario(**updates: object) -> EvaluationScenario:
    values: dict[str, object] = {
        "id": "test-scenario",
        "description": "A small repeatable test scenario.",
        "factory_name": "factory_01",
        "horizon_hour": 24,
        "step_hours": 0.25,
        "order_ids": ["ORD-001"],
        "events": [
            MachineFailureEvent(
                id="event-001",
                sim_hour=4,
                machine_id="M4",
                duration_hours=2,
            )
        ],
        "oracle_replan_event_ids": set(),
    }
    values.update(updates)
    return EvaluationScenario.model_validate(values)


def _agent_record(
    state: FactoryState,
    event: BaseEvent,
    *,
    should_replan: bool = True,
) -> AgentDecisionRecord:
    status = (
        DecisionStatus.REPLAN_RECOMMENDED if should_replan else DecisionStatus.NO_ACTION
    )
    return AgentDecisionRecord(
        factory_name=state.name,
        simulation_hour=state.sim_hour,
        schedule_version=state.schedule_version,
        state_snapshot_hash=state.snapshot_hash(),
        trigger_event_id=event.id,
        trigger_event_type=str(event.type),
        prompt_version="test",
        model_name="deterministic-test-model",
        decision=AgentDecision(
            status=status,
            severity=DecisionSeverity.HIGH if should_replan else DecisionSeverity.INFO,
            summary="Deterministic evaluation decision.",
            explanation="Produced by the injected test investigator.",
            should_replan=should_replan,
            requires_human_approval=should_replan,
        ),
    )


def test_scenario_files_are_valid_and_have_unique_ids() -> None:
    scenarios = load_scenarios()

    assert scenarios
    assert len({scenario.id for scenario in scenarios}) == len(scenarios)


def test_load_scenario_rejects_invalid_event_stream(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text(
        _scenario().model_dump_json().replace('"sim_hour":4.0', '"sim_hour":4.1'),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="align with step_hours"):
        load_scenario(path)


def test_scenario_rejects_unknown_oracle_event() -> None:
    with pytest.raises(ValidationError, match="oracle replan ids do not exist"):
        _scenario(oracle_replan_event_ids={"unknown-event"})


def test_scenario_hash_normalizes_oracle_event_order() -> None:
    events = [
        MachineFailureEvent(
            id="event-001",
            sim_hour=4,
            machine_id="M4",
            duration_hours=2,
        ),
        MachineFailureEvent(
            id="event-002",
            sim_hour=8,
            machine_id="M3",
            duration_hours=2,
        ),
    ]
    first = _scenario(
        events=events,
        oracle_replan_event_ids=["event-001", "event-002"],
    )
    second = _scenario(
        events=events,
        oracle_replan_event_ids=["event-002", "event-001"],
    )

    assert scenario_hash(first) == scenario_hash(second)


def test_policy_metrics_count_decisions_and_successful_replans() -> None:
    scenario = _scenario()

    no_op = run_scenario(scenario, NoOpPolicy())
    always = run_scenario(scenario, AlwaysReplanPolicy())

    assert no_op.metrics.replans == 0
    assert no_op.decision_event_ids == []
    assert always.metrics.replans == 1
    assert always.decision_event_ids == ["event-001"]
    assert always.metrics.model_calls == 0
    assert always.metrics.constraint_violations == 0
    assert always.decisions[0].event_id == "event-001"
    assert always.decisions[0].replan_requested is True
    assert always.decisions[0].schedule_committed is True


def test_metrics_measure_lateness_and_cost_from_final_state() -> None:
    scenario = _scenario(
        events=[
            MachineFailureEvent(
                id="event-001",
                sim_hour=4,
                machine_id="M5",
                duration_hours=20,
            )
        ]
    )

    result = run_scenario(scenario, NoOpPolicy())

    assert result.metrics.late_orders == 1
    assert result.metrics.priority_weighted_lateness == 12
    assert result.metrics.penalty_cost == 1080
    assert result.metrics.controllable_cost == pytest.approx(
        result.metrics.penalty_cost
        + result.metrics.overtime_cost
        + result.metrics.changeover_cost
    )
    assert result.metrics.total_cost == pytest.approx(
        result.metrics.production_cost + result.metrics.controllable_cost
    )


def test_controllable_cost_excludes_cost_of_goods() -> None:
    """A run that builds less must not look cheaper on the comparison metric."""
    idle = run_scenario(
        _scenario(
            events=[
                MachineFailureEvent(
                    id="event-001",
                    sim_hour=1,
                    machine_id="M5",
                    duration_hours=60,
                )
            ]
        ),
        NoOpPolicy(),
    )
    working = run_scenario(_scenario(), NoOpPolicy())

    assert idle.metrics.production_cost < working.metrics.production_cost
    assert idle.metrics.unmet_demand_units > working.metrics.unmet_demand_units
    assert idle.metrics.controllable_cost > working.metrics.controllable_cost


def test_oracle_uses_scenario_ground_truth() -> None:
    ignored = run_scenario(_scenario(), OraclePolicy())
    selected = run_scenario(
        _scenario(oracle_replan_event_ids={"event-001"}),
        OraclePolicy(),
    )

    assert ignored.decision_event_ids == []
    assert selected.decision_event_ids == ["event-001"]


def test_agent_policy_uses_injected_investigator_and_counts_calls() -> None:
    policy = AgentPolicy(lambda state, event: _agent_record(state, event))

    result = run_scenario(_scenario(), policy)

    assert result.policy_name == "agent"
    assert result.metrics.model_calls == 1
    assert result.metrics.replans == 1
    assert result.decision_event_ids == ["event-001"]
    assert policy.records[0].trigger_event_id == "event-001"


def test_agent_comparison_includes_agent_and_cp_sat_baselines() -> None:
    results = compare_with_agent(
        [_scenario()],
        lambda state, event: _agent_record(state, event, should_replan=False),
    )

    assert {result.policy_name for result in results} == {
        "no-op",
        "always-replan",
        "oracle",
        "agent",
    }
    agent = next(result for result in results if result.policy_name == "agent")
    assert agent.metrics.model_calls == 1


def test_initial_schedule_retries_a_cut_off_search_with_a_longer_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    budgets: list[float | None] = []
    committable = ScheduleResult(
        status=ScheduleStatus.OPTIMAL,
        validation=ValidationResult(),
    )

    def scheduler(
        state: FactoryState,
        request: OptimizeRequest | None = None,
    ) -> ScheduleResult:
        budgets.append(None if request is None else request.deterministic_time_limit)
        if len(budgets) == 1:
            return ScheduleResult(
                status=ScheduleStatus.UNKNOWN,
                solve_seconds=60.0,
                time_limit_seconds=60.0,
            )
        return committable

    monkeypatch.setattr(runner, "evaluation_scheduler", scheduler)

    result = runner._initial_cp_sat_schedule(_scenario())

    assert result is committable
    assert budgets == [None, runner.RETRY_DETERMINISTIC_BUDGET]


def test_initial_schedule_reports_an_unsolvable_scenario_with_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runner,
        "evaluation_scheduler",
        lambda state, request=None: ScheduleResult(
            status=ScheduleStatus.INFEASIBLE,
            solve_seconds=2.5,
            time_limit_seconds=60.0,
        ),
    )

    with pytest.raises(runner.InitialScheduleUnavailable) as caught:
        runner._initial_cp_sat_schedule(_scenario())

    assert caught.value.scenario_id == "test-scenario"
    assert "status=infeasible" in str(caught.value)
    assert "solve_seconds=2.5" in str(caught.value)


def test_events_marked_material_actually_disrupt_committed_work() -> None:
    """A scenario claiming a replan is warranted has to really lose work to it.

    assembly-line-failure used to fail M1, which the optimizer never scheduled
    anything on, so it silently became a copy of the deliberately inert
    unrelated-line-failure: same costs, same state hashes, nothing measured.
    """
    for scenario in load_scenarios():
        schedule = runner._initial_cp_sat_schedule(scenario)
        for event in scenario.events:
            machine_id = getattr(event, "machine_id", None)
            if event.id not in scenario.oracle_replan_event_ids or machine_id is None:
                continue

            failure_end = event.sim_hour + getattr(event, "duration_hours", 0.0)
            disrupted = [
                job
                for job in schedule.jobs
                if job.machine_id == machine_id
                and job.start_hour < failure_end
                and job.end_hour > event.sim_hour
            ]

            assert disrupted, (
                f"{scenario.id}: {event.id} is listed as an oracle replan, but "
                f"{machine_id} holds no committed work at hour {event.sim_hour}"
            )


def test_every_scenario_order_comes_due_inside_the_horizon() -> None:
    """An order due after the horizon is free to abandon, which rigs the ranking.

    Lateness only accrues once an order is past due, so a policy can dump work
    whose deadline falls outside the run and pay nothing for it — winning on
    cost while delivering less. Scenarios have to price everything they load.
    """
    for scenario in load_scenarios():
        state = runner._prepare_state(scenario)
        overdue = {
            order.id: order.due_hour
            for order in state.order_list()
            if order.due_hour > scenario.horizon_hour
        }

        assert not overdue, (
            f"{scenario.id}: horizon is {scenario.horizon_hour}h but {overdue} "
            f"come due after it, so abandoning them costs the policy nothing"
        )


def test_runs_are_isolated_and_repeatable() -> None:
    scenario = _scenario()

    first = run_scenario(scenario, AlwaysReplanPolicy())
    second = run_scenario(scenario, AlwaysReplanPolicy())

    assert first.deterministic_payload() == second.deterministic_payload()
    assert first.initial_state_hash == second.initial_state_hash
    assert first.final_state_hash == second.final_state_hash


def test_comparison_returns_every_scenario_policy_pair() -> None:
    scenarios = load_scenarios()

    results = compare_baselines(scenarios)

    assert len(results) == len(scenarios) * 3
    assert {result.policy_name for result in results} == {
        "no-op",
        "always-replan",
        "oracle",
    }


def test_cli_prints_header_when_no_scenarios_exist(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(evaluation_cli, "load_scenarios", lambda: [])

    evaluation_cli.main()

    output = capsys.readouterr().out
    assert "scenario" in output
    assert "policy" in output


def test_scenario_suite_separates_the_baseline_policies() -> None:
    """The suite must be able to tell the baselines apart in both directions.

    A comparison table where every row ties measures nothing, so the suite has
    to contain at least one scenario replanning clearly wins and one it clearly
    loses. Without both, an agent policy has no target to beat.
    """
    by_scenario: dict[str, dict[str, float]] = defaultdict(dict)
    for result in compare_baselines(load_scenarios()):
        by_scenario[result.scenario_id][result.policy_name] = (
            result.metrics.controllable_cost
        )

    assert any(
        costs["always-replan"] < costs["no-op"] for costs in by_scenario.values()
    ), "no scenario rewards replanning"
    assert any(
        costs["always-replan"] > costs["no-op"] for costs in by_scenario.values()
    ), "no scenario punishes replanning indiscriminately"

    # Ground truth should never be beaten by either fixed policy.
    for scenario_id, costs in by_scenario.items():
        assert costs["oracle"] <= costs["no-op"] + 1e-6, scenario_id
        assert costs["oracle"] <= costs["always-replan"] + 1e-6, scenario_id
