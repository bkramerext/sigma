"""Deterministic reference-only prompt-size estimates, not provider billing.

Provider usage covers full requests and cannot isolate the reference payload.
Use the same compact JSON serialization before and after compilation, with an
explicit approximate conversion of four UTF-8 bytes per token.
"""

from __future__ import annotations

import json
from typing import Any, TypedDict


class ReferenceTokenComparison(TypedDict):
    original_estimated_tokens: int
    compiled_estimated_tokens: int
    estimated_tokens_avoided_per_use: int
    estimated_reduction_percent: float


def estimate_tokens(payload: Any) -> int:
    """Approximate serialized reference material only; not a full provider request."""
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return (len(encoded) + 3) // 4


def compare(original: Any, compiled: Any) -> ReferenceTokenComparison:
    before = estimate_tokens(original)
    after = estimate_tokens(compiled)
    difference = before - after
    return {
        "original_estimated_tokens": before,
        "compiled_estimated_tokens": after,
        "estimated_tokens_avoided_per_use": difference,
        "estimated_reduction_percent": round(100.0 * difference / before, 1) if before else 0.0,
    }
