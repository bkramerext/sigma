"""Consistent dotenv-aware entrypoint for a separately launched backend."""

from fastapi import FastAPI

from sigma.local_config import load_local_config


def create_app() -> FastAPI:
    load_local_config()
    from sigma.api import app

    return app
