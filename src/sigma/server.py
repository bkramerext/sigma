"""Consistent dotenv-aware entrypoint for a separately launched backend."""

import logging
import os
import re
import subprocess
from pathlib import Path

from fastapi import FastAPI

from sigma.local_config import load_local_config


class _BuildAccessFormatter(logging.Formatter):
    def __init__(self, original: logging.Formatter, sha: str) -> None:
        super().__init__()
        self.original = original
        self.sha = sha

    def format(self, record: logging.LogRecord) -> str:
        return f"{self.original.format(record)} build={self.sha}"


def _build_sha() -> str:
    supplied = os.environ.get("SIGMA_BUILD_COMMIT") or os.environ.get("GITHUB_SHA")
    if supplied and re.fullmatch(r"[0-9a-fA-F]{7,40}", supplied):
        return supplied[:7].lower()
    try:
        checkout = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=checkout,
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        )
        return result.stdout.strip()[:7]
    except (OSError, subprocess.SubprocessError):
        return "unknown"


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
