"""Typed contracts shared by scheduling and validation."""

from __future__ import annotations

from enum import StrEnum

from pydantic import (
    BaseModel,
    Field,
    NonNegativeFloat,
    PositiveFloat,
)

from backend.simulator.models import ProductionJob


class ScheduleStatus(StrEnum):
    OPTIMAL = "optimal"
    FEASIBLE = "feasible"
    PARTIAL = "partial"
    INFEASIBLE = "infeasible"
    UNKNOWN = "unknown"
    ERROR = "error"


class ViolationCode(StrEnum):
    UNKNOWN_ORDER = "unknown_order"
    UNKNOWN_MACHINE = "unknown_machine"
    UNKNOWN_PRODUCT = "unknown_product"
    INCOMPATIBLE_MACHINE = "incompatible_machine"
    MACHINE_DOWN = "machine_down"
    OVERLAPPING_JOBS = "overlapping_jobs"
    INSUFFICIENT_INVENTORY = "insufficient_inventory"
    INVALID_QUANTITY = "invalid_quantity"


class ObjectiveWeights(BaseModel):
    late_delivery: NonNegativeFloat = 1.0
    overtime: NonNegativeFloat = 1.0
    changeover: NonNegativeFloat = 1.0


class OptimizeRequest(BaseModel):
    horizon_hours: PositiveFloat = 72.0
    bucket_hours: PositiveFloat = 1.0
    time_limit_seconds: PositiveFloat = 10.0
    weights: ObjectiveWeights = Field(
        default_factory=ObjectiveWeights,
    )
    hard_deadline_orders: list[str] = Field(
        default_factory=list,
    )


class ScheduleCost(BaseModel):
    late_penalty: NonNegativeFloat = 0.0
    overtime: NonNegativeFloat = 0.0
    changeover: NonNegativeFloat = 0.0

    @property
    def total(self) -> float:
        return round(
            self.late_penalty + self.overtime + self.changeover,
            2,
        )

    def weighted(self, weights: ObjectiveWeights) -> float:
        return round(
            self.late_penalty * weights.late_delivery
            + self.overtime * weights.overtime
            + self.changeover * weights.changeover,
            2,
        )


class ScheduleViolation(BaseModel):
    code: ViolationCode
    message: str
    job_ids: list[str] = Field(default_factory=list)
    order_ids: list[str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    violations: list[ScheduleViolation] = Field(
        default_factory=list,
    )

    @property
    def is_valid(self) -> bool:
        return not self.violations


class UnscheduledOrder(BaseModel):
    order_id: str
    reason_code: str
    explanation: str
    required_action: str | None = None


class ScheduleResult(BaseModel):
    status: ScheduleStatus
    jobs: list[ProductionJob] = Field(default_factory=list)
    unscheduled_orders: list[UnscheduledOrder] = Field(
        default_factory=list,
    )
    cost: ScheduleCost = Field(default_factory=ScheduleCost)
    optimality_gap: NonNegativeFloat | None = None
    solve_seconds: NonNegativeFloat = 0.0
    time_limit_seconds: NonNegativeFloat = 0.0
    relaxed_constraints: list[str] = Field(
        default_factory=list,
    )
    notes: list[str] = Field(default_factory=list)
    validation: ValidationResult | None = None

    @property
    def has_complete_schedule(self) -> bool:
        return self.status in (
            ScheduleStatus.OPTIMAL,
            ScheduleStatus.FEASIBLE,
        )

    @property
    def is_validated(self) -> bool:
        return self.validation is not None and self.validation.is_valid

    @property
    def is_committable(self) -> bool:
        return self.has_complete_schedule and self.is_validated
