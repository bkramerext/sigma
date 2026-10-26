"""Real API fixture for guest browser acceptance; no Google or provider calls."""

import os
from pathlib import Path

from sigma import cloud_auth
from sigma.api import app  # noqa: F401


def fixture_config() -> cloud_auth.Config:
    home = Path(os.environ["SIGMA_CLOUD_AUTH_HOME"])
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    return cloud_auth.Config(
        True,
        "fixture.apps.googleusercontent.com",
        "fixture-secret",
        os.environ["SIGMA_CLOUD_PUBLIC_ORIGIN"],
        "admin@example.test",
        home / "access.sqlite3",
        None,
        True,
    )


cloud_auth.config = fixture_config
