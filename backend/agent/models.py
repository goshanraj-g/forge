"""Typed contracts for agent investigations and decisions"""

from enum import StrEnum

from pydantic import BaseModel, Field


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
