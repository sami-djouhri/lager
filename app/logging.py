"""Structured logging setup. JSON in Prod, ConsoleRenderer im Dev."""

from __future__ import annotations

import logging
import os
import sys
from contextvars import ContextVar

import structlog

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def _add_request_id(_logger, _name, event_dict):
    rid = request_id_var.get()
    if rid is not None:
        event_dict["request_id"] = rid
    return event_dict


def configure_logging() -> None:
    log_format = os.environ.get("LOG_FORMAT", "json").lower()
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_request_id,
    ]

    if log_format == "console":
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level, logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )

    # Stdlib-Logging auf strukturierten Stream umlenken (uvicorn, sqlalchemy, …)
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        stream=sys.stderr,
        force=True,
    )


def get_logger(name: str | None = None):
    return structlog.get_logger(name)
