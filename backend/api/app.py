"""FastAPI application"""

import asyncio
import math
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, NoReturn

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.agent.models import AgentDecisionRecord
from backend.agent.observability import configure_agent_observability
from backend.agent.service import investigate_event
from backend.api.dependencies import (
    ActiveSimulator,
    AgentModel,
    AgentTimeout,
    LockedSimulator,
    PersistentRepository,
    get_investigation_snapshot,
)
from backend.api.schemas import (
    CommitScheduleRequest,
    CommitScheduleResponse,
    EvaluationComparisonResponse,
    EvaluationScenarioSummary,
    EventScheduledResponse,
    InvestigateEventRequest,
    RunUntilRequest,
    SimulationResponse,
    TickRequest,
)
from backend.evaluation.runner import compare_baselines, compare_with_agent
from backend.evaluation.scenarios import load_scenarios, scenario_hash
from backend.logging import configure_logging
from backend.optimizer.models import OptimizeRequest, ScheduleResult
from backend.optimizer.solver import optimize_schedule
from backend.optimizer.validator import validate_schedule
from backend.persistence.repository import PersistenceBatch
from backend.simulator.engine import FactorySimulator
from backend.simulator.events import BaseEvent, InjectableEvent
from backend.simulator.state import FactoryState

logger = structlog.get_logger(__name__)


class HealthResponse(BaseModel):
    status: str
    service: str


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    configure_agent_observability()
    yield


app = FastAPI(
    title="ForgeOps API",
    version="0.1.0",
    lifespan=lifespan,
)


def _sanitize_non_finite(value: Any) -> Any:
    """Replace inf/nan with their repr so the error body stays JSON-safe.

    Starlette's JSONResponse serializes with allow_nan=False, so echoing a
    rejected non-finite input (e.g. from `1e999`) back in the 422 body would
    otherwise crash the response encoder and surface as a 500.
    """
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {key: _sanitize_non_finite(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_non_finite(item) for item in value]
    return value


@app.exception_handler(RequestValidationError)
async def _handle_validation_error(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": _sanitize_non_finite(exc.errors())},
    )


def _persistence_unavailable(error: Exception) -> NoReturn:
    logger.exception("persistence_write_failed", error=str(error))
    raise HTTPException(
        status_code=503,
        detail="durable storage is temporarily unavailable",
    ) from error


def _publish(
    simulator: FactorySimulator,
    working: FactorySimulator,
    repository: PersistentRepository,
    batch: PersistenceBatch,
) -> None:
    try:
        repository.save(batch)
    except Exception as error:
        _persistence_unavailable(error)
    simulator.replace_with(working)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="forgeops",
    )


@app.get(
    "/factories/{name}",
    response_model=FactoryState,
)
def get_factory(simulator: ActiveSimulator) -> FactoryState:
    return simulator.state


@app.post(
    "/factories/{name}/tick",
    response_model=SimulationResponse,
)
def tick_factory(
    simulator: LockedSimulator,
    repository: PersistentRepository,
    request: TickRequest,
) -> SimulationResponse:
    working = simulator.clone()
    events = working.tick(request.step_hours)
    _publish(
        simulator,
        working,
        repository,
        PersistenceBatch(state=working.state, events=events),
    )

    return SimulationResponse(
        state=simulator.state,
        events=events,
    )


@app.post(
    "/factories/{name}/run-until",
    response_model=SimulationResponse,
)
def run_factory_until(
    simulator: LockedSimulator,
    repository: PersistentRepository,
    request: RunUntilRequest,
) -> SimulationResponse:
    working = simulator.clone()
    try:
        events = working.run_until(
            request.hour,
            request.step_hours,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error

    _publish(
        simulator,
        working,
        repository,
        PersistenceBatch(state=working.state, events=events),
    )

    return SimulationResponse(
        state=simulator.state,
        events=events,
    )


@app.post(
    "/factories/{name}/events",
    response_model=EventScheduledResponse,
    status_code=202,
)
def schedule_factory_event(
    simulator: LockedSimulator,
    repository: PersistentRepository,
    event: InjectableEvent,
) -> EventScheduledResponse:
    if event.sim_hour < simulator.state.sim_hour:
        raise HTTPException(
            status_code=409,
            detail="cannot schedule an event in the past",
        )

    working = simulator.clone()
    working.schedule(event)
    _publish(
        simulator,
        working,
        repository,
        PersistenceBatch(
            factory_name=working.state.name,
            events=[event],
            event_stage="scheduled",
        ),
    )

    return EventScheduledResponse(
        event=event,
        pending_event_count=len(simulator.pending),
    )


@app.post(
    "/factories/{name}/investigations",
    response_model=AgentDecisionRecord,
)
async def investigate_factory_event(
    name: str,
    model: AgentModel,
    timeout_seconds: AgentTimeout,
    repository: PersistentRepository,
    request: InvestigateEventRequest,
) -> AgentDecisionRecord:
    state, event = get_investigation_snapshot(name, request.event_id, repository)

    try:
        async with asyncio.timeout(timeout_seconds):
            record = await investigate_event(state, event, model)
    except TimeoutError as error:
        raise HTTPException(
            status_code=504,
            detail="agent investigation timed out",
        ) from error
    try:
        repository.save(PersistenceBatch(decision=record))
    except Exception as error:
        _persistence_unavailable(error)
    return record


@app.post(
    "/factories/{name}/optimize",
    response_model=ScheduleResult,
)
def optimize_factory(
    simulator: ActiveSimulator,
    request: OptimizeRequest,
) -> ScheduleResult:
    return optimize_schedule(
        simulator.state,
        request,
    )


@app.post(
    "/factories/{name}/schedules/commit",
    response_model=CommitScheduleResponse,
)
def commit_schedule(
    simulator: LockedSimulator,
    repository: PersistentRepository,
    request: CommitScheduleRequest,
) -> CommitScheduleResponse:
    state = simulator.state
    if request.expected_version != state.schedule_version:
        raise HTTPException(
            status_code=409,
            detail=(
                f"stale schedule version {request.expected_version}; "
                f"current version is {state.schedule_version}"
            ),
        )

    next_version = state.schedule_version + 1
    if any(job.schedule_version != next_version for job in request.jobs):
        raise HTTPException(
            status_code=409,
            detail=f"all jobs must target schedule version {next_version}",
        )

    validation = validate_schedule(
        state,
        request.jobs,
        set(request.hard_deadline_orders),
    )
    if not validation.is_valid:
        raise HTTPException(
            status_code=422,
            detail=[
                violation.model_dump(mode="json") for violation in validation.violations
            ],
        )

    scheduled_quantity = {
        order.id: sum(job.quantity for job in request.jobs if job.order_id == order.id)
        for order in state.open_orders()
    }
    incomplete_orders = [
        order.id
        for order in state.open_orders()
        if abs(scheduled_quantity[order.id] - order.remaining) > 1e-6
    ]
    if incomplete_orders:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "schedule does not cover every open order",
                "order_ids": incomplete_orders,
            },
        )

    committed_state = state.clone()
    committed_state.schedule_version = next_version
    # A version is a complete future plan, so commit replaces rather than merges it.
    committed_state.jobs = {job.id: job for job in request.jobs}
    try:
        repository.save(
            PersistenceBatch(
                state=committed_state,
                schedule=request.jobs,
            )
        )
    except Exception as error:
        _persistence_unavailable(error)
    simulator.state = committed_state

    return CommitScheduleResponse(
        state=committed_state,
        validation=validation,
    )


@app.get(
    "/evaluations",
    response_model=EvaluationComparisonResponse,
)
def compare_evaluation_baselines() -> EvaluationComparisonResponse:
    """Run every baseline policy against every scenario from clean initial states.

    Defined synchronously so FastAPI runs the solver in a worker thread rather
    than blocking the event loop.
    """
    scenarios = load_scenarios()

    return EvaluationComparisonResponse(
        scenarios=[
            EvaluationScenarioSummary(
                id=scenario.id,
                description=scenario.description,
                factory_name=scenario.factory_name,
                horizon_hour=scenario.horizon_hour,
                scenario_hash=scenario_hash(scenario),
                event_count=len(scenario.events),
            )
            for scenario in scenarios
        ],
        results=compare_baselines(scenarios),
    )


@app.post(
    "/evaluations/agent",
    response_model=EvaluationComparisonResponse,
)
def compare_agent_evaluation(
    model: AgentModel,
    timeout_seconds: AgentTimeout,
) -> EvaluationComparisonResponse:
    """Run the real agent and CP-SAT against every evaluation scenario.

    This is opt-in because it performs billable, nondeterministic model calls.
    FastAPI executes this synchronous route in a worker thread, where each
    asynchronous investigation can safely own its event loop.
    """
    scenarios = load_scenarios()

    async def investigate_with_timeout(
        state: FactoryState,
        event: BaseEvent,
    ) -> AgentDecisionRecord:
        try:
            async with asyncio.timeout(timeout_seconds):
                return await investigate_event(state, event, model)
        except TimeoutError as error:
            raise HTTPException(
                status_code=504,
                detail=f"agent evaluation timed out for event {event.id!r}",
            ) from error

    def investigator(state: FactoryState, event: BaseEvent) -> AgentDecisionRecord:
        return asyncio.run(investigate_with_timeout(state, event))

    return EvaluationComparisonResponse(
        scenarios=[
            EvaluationScenarioSummary(
                id=scenario.id,
                description=scenario.description,
                factory_name=scenario.factory_name,
                horizon_hour=scenario.horizon_hour,
                scenario_hash=scenario_hash(scenario),
                event_count=len(scenario.events),
            )
            for scenario in scenarios
        ],
        results=compare_with_agent(scenarios, investigator),
    )
