"""Consistent dotenv-aware entrypoint for a separately launched backend."""

import logging
from copy import copy

from fastapi import FastAPI

from sigma.build_info import build_commit
from sigma.local_config import load_local_config


class _BuildAccessFormatter(logging.Formatter):
    def __init__(self, original: logging.Formatter, sha: str) -> None:
        super().__init__()
        self.original = original
        self.sha = sha

    def format(self, record: logging.LogRecord) -> str:
        if isinstance(record.args, tuple) and len(record.args) == 5:
            labeled = copy(record)
            labeled.args = (f"{record.args[0]} {self.sha}", *record.args[1:])
            return self.original.format(labeled)
        return self.original.format(record)


def _build_sha() -> str:
    """Keep access-log tags aligned with the session's process-pinned build."""
    return build_commit()[:7]


def _label_access_log() -> None:
    sha = _build_sha()
    for handler in logging.getLogger("uvicorn.access").handlers:
        formatter = handler.formatter
        if formatter is not None and not isinstance(formatter, _BuildAccessFormatter):
            handler.setFormatter(_BuildAccessFormatter(formatter, sha))


def create_app() -> FastAPI:
    load_local_config()
    _label_access_log()
    from sigma.storage import validate_startup

    validate_startup()
    from sigma.api import app

    return app
