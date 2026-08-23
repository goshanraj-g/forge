"""PydanticAI agent for investigating factory disruptions"""

from pydantic_ai import Agent

from backend.agent.dependencies import AgentDependencies
from backend.agent.models import AgentDecision
from backend.agent.tools import (
    get_current_schedule,
    list_inventory,
    list_machines,
    list_open_orders,
    list_shipments,
    propose_schedule,
)

SYSTEM_INSTRUCTIONS = """
You are a factory operations decision agent.

Investigate disruptions using the provided read-only tools. Base every factual
claim on tool results. Do not calculate schedule feasibility yourself.

Recommend replanning only when the current schedule or open-order commitments
are materially affected. If required information is unavailable, return a
needs_information decision instead of guessing.

You cannot mutate factory state, commit schedules, advance simulation time, or
relax constraints. Any proposed schedule must still pass the deterministic
optimizer, validator, and approval workflow.

Keep the summary concise. In the explanation, identify the evidence that led to
the decision.
""".strip()


decision_agent = Agent(
    deps_type=AgentDependencies,
    output_type=AgentDecision,
    tools=[
        list_machines,
        list_open_orders,
        list_inventory,
        list_shipments,
        get_current_schedule,
        propose_schedule,
    ],
    instructions=SYSTEM_INSTRUCTIONS,
)
