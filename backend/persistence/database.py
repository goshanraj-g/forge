"""Database configuration and SQLModel session creation."""

from __future__ import annotations

import os
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

DEFAULT_DATABASE_URL = "sqlite:///./forgeops.db"


def build_engine(database_url: str, *, echo: bool = False) -> Engine:
    connect_args = (
        {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    )
    return create_engine(
        database_url,
        echo=echo,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


@lru_cache
def get_engine() -> Engine:
    return build_engine(os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL))


def create_schema(engine: Engine | None = None) -> None:
    SQLModel.metadata.create_all(engine or get_engine())


def session_factory() -> Session:
    return Session(get_engine())


def get_session() -> Iterator[Session]:
    with session_factory() as session:
        yield session
