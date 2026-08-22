import pytest
from pydantic import ValidationError

from backend.optimizer.models import (
    ObjectiveWeights,
    OptimizeRequest,
    ScheduleCost,
    ScheduleResult,
    ScheduleStatus,
    ScheduleViolation,
    ValidationResult,
    ViolationCode,
)


def test_schedule_cost_reports_total_and_weighted_cost() -> None:
    cost = ScheduleCost(
        late_penalty=100,
        overtime=40,
        changeover=20,
    )
    weights = ObjectiveWeights(
        late_delivery=2,
        overtime=0.5,
        changeover=1,
    )

    assert cost.total == 160
    assert cost.weighted(weights) == 240


@pytest.mark.parametrize(
    ("status", "complete"),
    [
        (ScheduleStatus.OPTIMAL, True),
        (ScheduleStatus.FEASIBLE, True),
        (ScheduleStatus.PARTIAL, False),
        (ScheduleStatus.INFEASIBLE, False),
        (ScheduleStatus.UNKNOWN, False),
        (ScheduleStatus.ERROR, False),
    ],
)
def test_only_complete_statuses_have_complete_schedule(
    status: ScheduleStatus,
    complete: bool,
) -> None:
    assert ScheduleResult(status=status).has_complete_schedule is complete


def test_schedule_requires_successful_validation_to_be_committable() -> None:
    unvalidated = ScheduleResult(status=ScheduleStatus.FEASIBLE)
    valid = ScheduleResult(
        status=ScheduleStatus.FEASIBLE,
        validation=ValidationResult(),
    )
    invalid = ScheduleResult(
        status=ScheduleStatus.FEASIBLE,
        validation=ValidationResult(
            violations=[
                ScheduleViolation(
                    code=ViolationCode.UNKNOWN_MACHINE,
                    message="machine does not exist",
                ),
            ],
        ),
    )

    assert not unvalidated.is_committable
    assert valid.is_committable
    assert not invalid.is_committable


def test_request_rejects_nonpositive_solver_settings() -> None:
    with pytest.raises(ValidationError):
        OptimizeRequest(bucket_hours=0)

    with pytest.raises(ValidationError):
        OptimizeRequest(time_limit_seconds=-1)


def test_result_collections_are_not_shared() -> None:
    first = ScheduleResult(status=ScheduleStatus.UNKNOWN)
    second = ScheduleResult(status=ScheduleStatus.UNKNOWN)

    first.notes.append("timed out")

    assert second.notes == []
