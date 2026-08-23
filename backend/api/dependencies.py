"""Dependencies shared by API routes."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException
from pydantic_ai.models import Model

from backend.agent.config import AgentSettings, build_production_model
from backend.api.store import factory_store
from backend.simulator.engine import FactorySimulator


def get_simulator(name: str) -> FactorySimulator:
    try:
        return factory_store.get(name)
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail=f"unknown factory {name!r}",
        ) from error


def get_locked_simulator(name: str) -> Iterator[FactorySimulator]:
    try:
        with factory_store.locked(name) as simulator:
            yield simulator
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail=f"unknown factory {name!r}",
        ) from error


def get_agent_model() -> Model:
    try:
        settings = AgentSettings.from_environment()
    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error

    return build_production_model(settings)


ActiveSimulator = Annotated[
    FactorySimulator,
    Depends(get_simulator),
]

LockedSimulator = Annotated[
    FactorySimulator,
    Depends(get_locked_simulator),
]

AgentModel = Annotated[
    Model,
    Depends(get_agent_model),
]
