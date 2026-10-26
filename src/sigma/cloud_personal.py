"""Hosted personal-model adapter boundary.

Hosted ChatGPT-plan authorization is intentionally unavailable until SIGMA has
an approved OpenAI access path. This module must never inspect or borrow the
designated sponsor connection. Per-subject storage isolation is provided by
``ai_store`` for a future approved adapter.
"""

from __future__ import annotations

from sigma.openai_connection import AuthContext

UNAVAILABLE_GUIDANCE = (
    "Personal ChatGPT authentication is not available in hosted SIGMA yet. "
    "Your personal credentials are not transferred or used. Choose sponsored "
    "access explicitly if it is available, or continue with saved research."
)


def auth_context(subject_hash: str | None) -> AuthContext:
    """Return a non-credential context until a supported hosted adapter exists."""
    identity = "cloud_personal_unavailable:" + (subject_hash or "unbound")
    return AuthContext(
        token="",
        mode="chatgpt",
        status="unavailable",
        identity=identity,
    )
