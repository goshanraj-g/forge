"""Application service for running factory investigations"""

from pydantic_ai.models import Model

from backend.agent.decision_agent import decision_agent
from backend.agent.dependencies import AgentDependencies
from backend.agent.models import AgentDecision, AgentDecisionRecord
from backend.simulator.events import BaseEvent
from backend.simulator.state import FactoryState


async def investigate_factory(
    state: FactoryState,
    prompt: str,
    model: Model,
) -> AgentDecision:
    dependencies = AgentDependencies.from_state(state)

    result = await decision_agent.run(
        prompt,
        deps=dependencies,
        model=model,
    )

    return result.output


async def investigate_event(
    state: FactoryState,
    event: BaseEvent,
    model: Model,
) -> AgentDecisionRecord:
    snapshot_hash = state.snapshot_hash()

    prompt = (
        "Investigate this factory event and determine the appropriate response.\n"
        f"Event: {event.model_dump_json()}"
    )

    decision = await investigate_factory(
        state,
        prompt,
        model,
    )

    return AgentDecisionRecord(
        factory_name=state.name,
        simulation_hour=state.sim_hour,
        schedule_version=state.schedule_version,
        state_snapshot_hash=snapshot_hash,
        trigger_event_id=event.id,
        trigger_event_type=str(event.type),
        decision=decision,
    )
