"""Structured logging configuration shared by API and workers."""

import logging
import os

import structlog


def configure_logging() -> None:
    logging.basicConfig(
        format="%(message)s",
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )
