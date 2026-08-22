"""FastAPI application"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from backend.api.store import factory_store
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
def get_factory(name: str) -> FactoryState:
    try:
        return factory_store.get(name).state
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail=f"unknown factory {name!r}",
        ) from error
