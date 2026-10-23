"""Browser fixture for crash recovery during an in-flight fake provider call."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import cloud_workspace_test_app

from sigma import research_sessions

app = cloud_workspace_test_app.app
credential = {
    "mode": "api_key",
    "identity": "cloud_service_api_key",
    "token": "deterministic-browser-fixture",
    "status": "connected",
}
configuration = {
    "available": True,
    "model": "gpt-6.1-sol",
    "reasoning_effort": "high",
}
research_sessions.auth_context = AsyncMock(return_value=credential)
research_sessions.configuration = AsyncMock(return_value=configuration)
research_sessions.execution_capabilities = list


async def blocked_fake_call(
    record: dict[str, Any], role: str, context: dict[str, Any], timeout_seconds: float | None = None
):
    del role, context, timeout_seconds
    marker = Path(os.environ["SIGMA_CLOUD_TEST_DISPATCH_LOG"])

    def record_dispatch() -> None:
        with marker.open("a", encoding="utf-8") as output:
            output.write(f"{record['id']}\n")
            output.flush()
            os.fsync(output.fileno())

    await asyncio.to_thread(record_dispatch)
    await asyncio.Future()


research_sessions._call = blocked_fake_call
