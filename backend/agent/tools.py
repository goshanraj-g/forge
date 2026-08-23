"""Read-only tools available to the factory decision agent"""

from pydantic_ai import RunContext

from backend.agent.dependencies import AgentDependencies
from backend.agent.models import FactoryClock
from backend.optimizer.models import OptimizeRequest, ScheduleResult
from backend.optimizer.solver import optimize_schedule
from backend.simulator.models import (
    InventoryItem,
    Machine,
    Order,
    Product,
    ProductionJob,
    Shipment,
)


def get_factory_clock(
    ctx: RunContext[AgentDependencies],
) -> FactoryClock:
    """Return the factory's current simulation time and schedule version."""
    state = ctx.deps.state
    return FactoryClock(
        factory_name=state.name,
        sim_hour=state.sim_hour,
        schedule_version=state.schedule_version,
    )


def list_machines(
    ctx: RunContext[AgentDependencies],
) -> list[Machine]:
    """Return every machine, including capabilities, status, and downtime."""
    return ctx.deps.state.machine_list()


def list_open_orders(
    ctx: RunContext[AgentDependencies],
) -> list[Order]:
    """Return orders with remaining production demand and their due hours."""
    return ctx.deps.state.open_orders()


def list_products(
    ctx: RunContext[AgentDependencies],
) -> list[Product]:
    """Return product definitions, families, and bills of material."""
    return ctx.deps.state.product_list()


def list_inventory(
    ctx: RunContext[AgentDependencies],
) -> list[InventoryItem]:
    """Return current on-hand quantities for every inventory component."""
    return ctx.deps.state.inventory_list()


def list_shipments(
    ctx: RunContext[AgentDependencies],
) -> list[Shipment]:
    """Return inbound component shipments, quantities, statuses, and ETAs."""
    return ctx.deps.state.shipment_list()


def get_current_schedule(
    ctx: RunContext[AgentDependencies],
) -> list[ProductionJob]:
    """Return the currently committed production jobs; an empty list means none."""
    return ctx.deps.state.job_list()


def propose_schedule(
    ctx: RunContext[AgentDependencies],
) -> ScheduleResult:
    """Generate a validated schedule candidate without committing it."""
    request = OptimizeRequest(
        horizon_hours=72,
        bucket_hours=1,
        time_limit_seconds=5,
    )

    return optimize_schedule(
        ctx.deps.state,
        request,
    )
