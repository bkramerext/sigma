"""The single credential-free dispatch boundary for SIGMA Personal --prod inference.

All model-generating features use this boundary before any direct bearer HTTP.
Sponsored/API and normal-local ChatGPT continue using their existing transports.
A selected Personal worker that fails NEVER falls back to another funding mode.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import uuid4

from sigma.projects import ProjectError


def uses_personal_worker(binding: Mapping[str, Any]) -> bool:
    return binding.get("transport") == "personal_worker"


async def private_response_if_selected(
    binding: Mapping[str, Any],
    payload: dict[str, Any],
    *,
    timeout_seconds: float,
    request_id: str | None = None,
) -> dict[str, Any] | None:
    """Return worker response when Personal is selected; otherwise dispatch nothing.

    A None result means *only* that a different, explicitly selected transport
    must run. Worker errors propagate and never silently fall back to sponsored.
    """
    if not uses_personal_worker(binding):
        return None
    if (
        binding.get("mode") != "chatgpt"
        or binding.get("status") != "connected"
        or binding.get("token")
        or not isinstance(binding.get("worker_binding"), str)
    ):
        raise ProjectError("Invalid isolated Personal ChatGPT connection.")
    # Import lazily so non-Personal callers do not initialize the Docker adapter.
    from sigma import personal_inference

    return await personal_inference.respond(
        payload,
        expected_binding=binding["worker_binding"],
        request_id=request_id or uuid4().hex,
        timeout_seconds=timeout_seconds,
    )
