"""Append-only SQLModel records for operational and evaluation artifacts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


def _record_id() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class FactorySnapshotRow(SQLModel, table=True):
    __tablename__ = "factory_snapshots"

    id: str = Field(default_factory=_record_id, primary_key=True)
    factory_name: str = Field(index=True)
    simulation_hour: float
    schedule_version: int
    snapshot_hash: str = Field(index=True)
    payload: dict[str, Any] = Field(sa_type=JSON)
    created_at: datetime = Field(default_factory=_now)


class EventRecordRow(SQLModel, table=True):
    __tablename__ = "factory_events"
    __table_args__ = (UniqueConstraint("factory_name", "event_id"),)

    id: str = Field(default_factory=_record_id, primary_key=True)
    factory_name: str = Field(index=True)
    event_id: str = Field(index=True)
    event_type: str = Field(index=True)
    simulation_hour: float
    payload: dict[str, Any] = Field(sa_type=JSON)
    created_at: datetime = Field(default_factory=_now)


class ScheduleRecordRow(SQLModel, table=True):
    __tablename__ = "factory_schedules"
    __table_args__ = (UniqueConstraint("factory_name", "schedule_version"),)

    id: str = Field(default_factory=_record_id, primary_key=True)
    factory_name: str = Field(index=True)
    schedule_version: int
    state_snapshot_hash: str
    payload: dict[str, Any] = Field(sa_type=JSON)
    created_at: datetime = Field(default_factory=_now)


class DecisionRecordRow(SQLModel, table=True):
    __tablename__ = "agent_decisions"

    id: str = Field(default_factory=_record_id, primary_key=True)
    factory_name: str = Field(index=True)
    trigger_event_id: str = Field(index=True)
    state_snapshot_hash: str = Field(index=True)
    prompt_version: str
    model_name: str
    payload: dict[str, Any] = Field(sa_type=JSON)
    created_at: datetime = Field(default_factory=_now)


class EvaluationRecordRow(SQLModel, table=True):
    __tablename__ = "evaluation_results"

    id: str = Field(default_factory=_record_id, primary_key=True)
    scenario_id: str = Field(index=True)
    policy_name: str = Field(index=True)
    scenario_hash: str = Field(index=True)
    final_state_hash: str
    payload: dict[str, Any] = Field(sa_type=JSON)
    created_at: datetime = Field(default_factory=_now)


class DecisionMemoryRow(SQLModel, table=True):
    """Optional vector index populated only when retrieval is enabled."""

    __tablename__ = "decision_memories"

    id: str = Field(default_factory=_record_id, primary_key=True)
    decision_id: str = Field(index=True, unique=True)
    content: str
    embedding: list[float] | None = Field(
        default=None,
        sa_column=Column(Vector(1536), nullable=True),
    )
    created_at: datetime = Field(default_factory=_now)
