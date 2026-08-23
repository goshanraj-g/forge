"""Read-only tools available to the factory decision agent"""

from pydantic_ai import RunContext

from backend.agent.dependencies import AgentDependencies
from backend.simulator.models import (
    InventoryItem,
    Machine,
    Order,
    ProductionJob,
    Shipment,
)


def list_machines(
    ctx: RunContext[AgentDependencies],
) -> list[Machine]:
    return ctx.deps.state.machine_list()


def list_open_orders(
    ctx: RunContext[AgentDependencies],
) -> list[Order]:
    return ctx.deps.state.open_orders()


def list_inventory(
    ctx: RunContext[AgentDependencies],
) -> list[InventoryItem]:
    return ctx.deps.state.inventory_list()


def list_shipments(
    ctx: RunContext[AgentDependencies],
) -> list[Shipment]:
    return ctx.deps.state.shipment_list()


def get_current_schedule(
    ctx: RunContext[AgentDependencies],
) -> list[ProductionJob]:
    return ctx.deps.state.job_list()
