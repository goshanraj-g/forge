"""Create durable ForgeOps records and pgvector support.

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _record_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    ]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "factory_snapshots",
        sa.Column("sequence", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("id", sa.String(), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("factory_name", sa.String(), nullable=False),
        sa.Column("simulation_hour", sa.Float(), nullable=False),
        sa.Column("schedule_version", sa.Integer(), nullable=False),
        sa.Column("snapshot_hash", sa.String(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
    )
    op.create_index("ix_factory_snapshots_id", "factory_snapshots", ["id"])
    op.create_index(
        "ix_factory_snapshots_factory_name", "factory_snapshots", ["factory_name"]
    )
    op.create_index(
        "ix_factory_snapshots_snapshot_hash", "factory_snapshots", ["snapshot_hash"]
    )
    op.create_table(
        "factory_events",
        *_record_columns(),
        sa.Column("factory_name", sa.String(), nullable=False),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("event_stage", sa.String(), nullable=False),
        sa.Column("simulation_hour", sa.Float(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.UniqueConstraint("factory_name", "event_id", "event_stage"),
    )
    op.create_index(
        "ix_factory_events_factory_name", "factory_events", ["factory_name"]
    )
    op.create_index("ix_factory_events_event_id", "factory_events", ["event_id"])
    op.create_index("ix_factory_events_event_type", "factory_events", ["event_type"])
    op.create_index("ix_factory_events_event_stage", "factory_events", ["event_stage"])
    op.create_table(
        "factory_schedules",
        *_record_columns(),
        sa.Column("factory_name", sa.String(), nullable=False),
        sa.Column("schedule_version", sa.Integer(), nullable=False),
        sa.Column("state_snapshot_hash", sa.String(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.UniqueConstraint("factory_name", "schedule_version"),
    )
    op.create_index(
        "ix_factory_schedules_factory_name", "factory_schedules", ["factory_name"]
    )
    op.create_table(
        "agent_decisions",
        *_record_columns(),
        sa.Column("factory_name", sa.String(), nullable=False),
        sa.Column("trigger_event_id", sa.String(), nullable=False),
        sa.Column("state_snapshot_hash", sa.String(), nullable=False),
        sa.Column("prompt_version", sa.String(), nullable=False),
        sa.Column("model_name", sa.String(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
    )
    op.create_index(
        "ix_agent_decisions_factory_name", "agent_decisions", ["factory_name"]
    )
    op.create_index(
        "ix_agent_decisions_trigger_event_id", "agent_decisions", ["trigger_event_id"]
    )
    op.create_index(
        "ix_agent_decisions_state_snapshot_hash",
        "agent_decisions",
        ["state_snapshot_hash"],
    )
    op.create_table(
        "evaluation_results",
        *_record_columns(),
        sa.Column("scenario_id", sa.String(), nullable=False),
        sa.Column("policy_name", sa.String(), nullable=False),
        sa.Column("scenario_hash", sa.String(), nullable=False),
        sa.Column("final_state_hash", sa.String(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
    )
    op.create_index(
        "ix_evaluation_results_scenario_id", "evaluation_results", ["scenario_id"]
    )
    op.create_index(
        "ix_evaluation_results_policy_name", "evaluation_results", ["policy_name"]
    )
    op.create_index(
        "ix_evaluation_results_scenario_hash", "evaluation_results", ["scenario_hash"]
    )
    op.create_table(
        "decision_memories",
        *_record_columns(),
        sa.Column("decision_id", sa.String(), nullable=False, unique=True),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
    )
    op.create_index(
        "ix_decision_memories_decision_id", "decision_memories", ["decision_id"]
    )


def downgrade() -> None:
    op.drop_table("decision_memories")
    op.drop_table("evaluation_results")
    op.drop_table("agent_decisions")
    op.drop_table("factory_schedules")
    op.drop_table("factory_events")
    op.drop_table("factory_snapshots")
