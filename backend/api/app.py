"""FastAPI application"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from backend.api.dependencies import ActiveSimulator
from backend.api.schemas import (
    RunUntilRequest,
    SimulationResponse,
    TickRequest,
)
from backend.simulator.state import FactoryState


class HealthResponse(BaseModel):
    status: str
    service: str


app = FastAPI(
    title="ForgeOps API",
    version="0.1.0",
)


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
    simulator: ActiveSimulator,
    request: TickRequest,
) -> SimulationResponse:
    events = simulator.tick(request.step_hours)

    return SimulationResponse(
        state=simulator.state,
        events=events,
    )


@app.post(
    "/factories/{name}/run-until",
    response_model=SimulationResponse,
)
def run_factory_until(
    simulator: ActiveSimulator,
    request: RunUntilRequest,
) -> SimulationResponse:
    try:
        events = simulator.run_until(
            request.hour,
            request.step_hours,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error

    return SimulationResponse(
        state=simulator.state,
        events=events,
    )
