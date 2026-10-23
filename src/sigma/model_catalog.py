"""Reviewed Responses/text/strict JSON/reasoning capabilities, verified 2026-10-20.

Sources: https://developers.openai.com/api/docs/models/gpt-6.1-sol
https://developers.openai.com/api/docs/models/gpt-6-luna
https://developers.openai.com/api/docs/models/gpt-6-astra
We deliberately expose four common efforts, not every provider effort.
"""

import os
import re

DEFAULT_MODEL = "gpt-6.1-sol"
EFFORTS = ("low", "medium", "high", "xhigh")
# Relative tiers reflect published API token prices checked 2026-10-22:
# Luna $0.10/$0.50, Sol $2/$10, and Astra $10/$50 per million input/output
# tokens. These symbols are not estimates of a research session's charges.
CATALOG = {
    "gpt-6.1-sol": {
        "label": "Sol · Balanced ($$)",
        "relative_cost": "$$",
        "description": "Balance research capability and cost.",
        "efforts": EFFORTS,
    },
    "gpt-6-luna": {
        "label": "Luna · Economy ($)",
        "relative_cost": "$",
        "description": "Lower-cost exploration of focused questions.",
        "efforts": EFFORTS,
    },
    "gpt-6-astra": {
        "label": "Astra · Advanced ($$$)",
        "relative_cost": "$$$",
        "description": "For the most demanding research reasoning; higher cost.",
        "efforts": EFFORTS,
    },
}


def legacy_model() -> str:
    override = os.environ.get("SIGMA_AI_MODEL", "")
    return override if override in CATALOG else DEFAULT_MODEL


def validate_stored(model: str, effort: str) -> None:
    # A persisted selection must survive a future catalog removal.
    if (
        not isinstance(model, str)
        or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,99}", model)
        or effort not in EFFORTS
    ):
        raise ValueError("Invalid model ID or Thinking level")


def validate_pair(model: str, effort: str) -> None:
    validate_stored(model, effort)
    if model not in CATALOG or effort not in CATALOG[model]["efforts"]:
        raise ValueError(
            "Selected model/Thinking level is not in the reviewed compatible catalog; choose a supported pair explicitly"
        )
