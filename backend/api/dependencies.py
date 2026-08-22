"""Dependencies shared by API routes."""

from typing import Annotated

from fastapi import Depends, HTTPException

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


ActiveSimulator = Annotated[
    FactorySimulator,
    Depends(get_simulator),
]
