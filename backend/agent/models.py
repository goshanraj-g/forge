"""Typed contracts for agent investigations and decisions"""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field, model_validator


class DecisionSeverity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DecisionStatus(StrEnum):
    NO_ACTION = "no_action"
    REPLAN_RECOMMENDED = "replan_recommended"
    NEEDS_INFORMATION = "needs_information"
    ESCALATE = "escalate"


class FactoryClock(BaseModel):
    factory_name: str
    sim_hour: float
    schedule_version: int


class AgentDecision(BaseModel):
    status: DecisionStatus
    severity: DecisionSeverity
    summary: str = Field(min_length=1)
    explanation: str = Field(min_length=1)

    affected_order_ids: list[str] = Field(default_factory=list)
    affected_machine_ids: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)

    should_replan: bool = False
    requires_human_approval: bool = False

    @model_validator(mode="after")
    def validate_consistency(self) -> Self:
        should_replan = self.status == DecisionStatus.REPLAN_RECOMMENDED
        if self.should_replan != should_replan:
            raise ValueError("should_replan must be true only for replan_recommended")

        approval_required = self.status in (
            DecisionStatus.REPLAN_RECOMMENDED,
            DecisionStatus.ESCALATE,
        )
        if self.requires_human_approval != approval_required:
            raise ValueError("replanning and escalation require human approval")

        if (
            self.status == DecisionStatus.NEEDS_INFORMATION
            and not self.missing_information
        ):
            raise ValueError(
                "a needs_information decision must identify missing information"
            )

        return self


class AgentDecisionRecord(BaseModel):
    factory_name: str
    simulation_hour: float
    schedule_version: int
    state_snapshot_hash: str

    trigger_event_id: str
    trigger_event_type: str

    decision: AgentDecision
