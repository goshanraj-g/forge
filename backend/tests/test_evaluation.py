from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.evaluation.models import EvaluationScenario
from backend.evaluation.policies import AlwaysReplanPolicy, NoOpPolicy, OraclePolicy
from backend.evaluation.runner import compare_baselines, run_scenario
from backend.evaluation.scenarios import load_scenario, load_scenarios, scenario_hash
from backend.simulator.events import MachineFailureEvent


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
    assert result.metrics.total_cost == pytest.approx(
        result.metrics.production_cost + result.metrics.penalty_cost
    )


def test_oracle_uses_scenario_ground_truth() -> None:
    ignored = run_scenario(_scenario(), OraclePolicy())
    selected = run_scenario(
        _scenario(oracle_replan_event_ids={"event-001"}),
        OraclePolicy(),
    )

    assert ignored.decision_event_ids == []
    assert selected.decision_event_ids == ["event-001"]


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
