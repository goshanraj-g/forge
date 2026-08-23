"""Dependencies shared by API routes."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException
from pydantic_ai.models import Model

from backend.agent.config import AgentSettings, build_production_model
from backend.api.store import factory_store
from backend.persistence.database import session_factory
from backend.persistence.repository import Repository, SQLRepository
from backend.simulator.engine import FactorySimulator
from backend.simulator.events import BaseEvent
from backend.simulator.state import FactoryState


def get_repository() -> Repository:
    return SQLRepository(session_factory)


RepositoryDependency = Annotated[Repository, Depends(get_repository)]


def _recover_simulator(name: str, repository: Repository) -> FactorySimulator | None:
    recovery = repository.recover_factory(name)
    if recovery is None:
        return None
    simulator = FactorySimulator(recovery.state)
    simulator.pending = recovery.pending
    simulator.log = recovery.log
    simulator.context.restore_id_counter(
        [event.id for event in [*recovery.pending, *recovery.log]]
    )
    return simulator


def get_simulator(
    name: str,
    repository: RepositoryDependency,
) -> FactorySimulator:
    try:
        return factory_store.get(
            name,
            lambda factory: _recover_simulator(factory, repository),
        )
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail=f"unknown factory {name!r}",
        ) from error


def get_locked_simulator(
    name: str,
    repository: RepositoryDependency,
) -> Iterator[FactorySimulator]:
    try:
        with factory_store.locked(
            name,
            lambda factory: _recover_simulator(factory, repository),
        ) as simulator:
            yield simulator
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail=f"unknown factory {name!r}",
        ) from error


def get_investigation_snapshot(
    name: str,
    event_id: str,
    repository: Repository,
) -> tuple[FactoryState, BaseEvent]:
    """Atomically copy the state and processed event used by an investigation."""
    try:
        with factory_store.locked(
            name,
            lambda factory: _recover_simulator(factory, repository),
        ) as simulator:
            event = next(
                (event for event in reversed(simulator.log) if event.id == event_id),
                None,
            )
            if event is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"processed event {event_id!r} was not found",
                )

            return simulator.state.clone(), event.model_copy(deep=True)
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


def get_agent_timeout() -> float:
    try:
        return AgentSettings.from_environment().timeout_seconds
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


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
AgentTimeout = Annotated[float, Depends(get_agent_timeout)]

PersistentRepository = RepositoryDependency
