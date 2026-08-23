import pytest
from pydantic import ValidationError

from backend.agent.models import (
    AgentDecision,
    DecisionSeverity,
    DecisionStatus,
)


def decision(**changes: object) -> AgentDecision:
    values: dict[str, object] = {
        "status": DecisionStatus.NO_ACTION,
        "severity": DecisionSeverity.INFO,
        "summary": "Operations are stable.",
        "explanation": "No current commitments are affected.",
    }
    values.update(changes)
    return AgentDecision.model_validate(values)


def test_accepts_consistent_replan_decision() -> None:
    result = decision(
        status=DecisionStatus.REPLAN_RECOMMENDED,
        severity=DecisionSeverity.HIGH,
        should_replan=True,
        requires_human_approval=True,
        affected_order_ids=["ORD-001"],
    )

    assert result.should_replan is True


def test_no_action_cannot_request_replanning() -> None:
    with pytest.raises(ValidationError, match="should_replan"):
        decision(should_replan=True)


def test_replan_status_must_request_replanning() -> None:
    with pytest.raises(ValidationError, match="should_replan"):
        decision(
            status=DecisionStatus.REPLAN_RECOMMENDED,
            requires_human_approval=True,
        )


def test_replan_requires_human_approval() -> None:
    with pytest.raises(ValidationError, match="human approval"):
        decision(
            status=DecisionStatus.REPLAN_RECOMMENDED,
            should_replan=True,
        )


def test_escalation_requires_human_approval() -> None:
    with pytest.raises(ValidationError, match="human approval"):
        decision(status=DecisionStatus.ESCALATE)


def test_needs_information_must_name_missing_information() -> None:
    with pytest.raises(ValidationError, match="missing information"):
        decision(status=DecisionStatus.NEEDS_INFORMATION)


def test_accepts_needs_information_with_required_fields() -> None:
    result = decision(
        status=DecisionStatus.NEEDS_INFORMATION,
        missing_information=["supplier recovery estimate"],
    )

    assert result.missing_information == ["supplier recovery estimate"]
