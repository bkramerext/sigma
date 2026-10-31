#!/usr/bin/env python3
"""Derive *conditional* MindRouter energy/TCO break-even bounds from PEARC'26.

Not a measurement of per-model efficiency, research quality, or total cost.
Published daily power and commercial API equivalents are approximate.
"""
from __future__ import annotations

import argparse
import json
import math
from typing import Any

SOURCE = (
    "Lucas Sheneman, MindRouter: Open-Source LLM Inference Gateway "
    "for Institutional AI Sovereignty, PEARC'26, DOI:10.1145/3785462.3815861"
)
SOURCE_URL = (
    "https://ai4ra.uidaho.edu/wp-content/uploads/2026/04/"
    "Sheneman_MindRouter_PEARC26_Short_Paper.pdf"
)
TOKENS = 872_997_430
DAYS = 17
APPROX_KWH_PER_DAY = 275.0
API_EQUIVALENT_USD = (4027.0, 11896.0)


def finite_nonnegative(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return result


def derive(
    electricity_usd_per_kwh: float = 0.12,
    local_to_api_task_success_ratio: float = 1.0,
) -> dict[str, Any]:
    """Cost-equivalence envelope assuming *comparable workload and tasks*.

    Let r = P(local useful completion)/P(API useful completion).
    Local is no more expensive per successful useful task only when:
      local_energy + local_nonenergy_overhead <= r * API_proxy_cost.
    No success rate or workload equivalence is established in the source.
    """
    tariff = finite_nonnegative(electricity_usd_per_kwh, "electricity_usd_per_kwh")
    quality_ratio = finite_nonnegative(
        local_to_api_task_success_ratio, "local_to_api_task_success_ratio"
    )
    energy = DAYS * APPROX_KWH_PER_DAY
    electricity = energy * tariff
    low, high = API_EQUIVALENT_USD
    return {
        "source": SOURCE,
        "source_url": SOURCE_URL,
        "provenance": {
            "tokens": "reported processed tokens, March 2026 17-day window",
            "kwh": "DERIVED from approximate normal daily energy, NOT directly metered same window",
            "api_usd": "published price-based API-equivalent ESTIMATES, not a matched quality test",
            "tariff": "illustrative input, not observed Idaho electricity tariff",
            "quality_ratio": "hypothetical parameter, not measured",
        },
        "observed_period_days": DAYS,
        "reported_tokens": TOKENS,
        "approx_normal_kwh_per_day": APPROX_KWH_PER_DAY,
        "approx_energy_kwh_over_window": round(energy, 3),
        "derived_tokens_per_kwh": round(TOKENS / energy, 2),
        "derived_wh_per_1000_tokens": round(energy * 1000 / (TOKENS / 1000), 4),
        "illustrative_tariff_usd_per_kwh": tariff,
        "illustrative_electricity_cost_usd": round(electricity, 2),
        "electricity_only_usd_per_million_tokens": round(
            electricity / TOKENS * 1_000_000, 4
        ),
        "published_api_equivalent_usd_range": [low, high],
        "published_api_equivalent_usd_per_million_tokens": [
            round(low / TOKENS * 1_000_000, 4),
            round(high / TOKENS * 1_000_000, 4),
        ],
        "hypothetical_local_to_api_success_ratio": quality_ratio,
        "max_nonenergy_cost_for_equal_cost_per_useful_success_usd_17d": [
            round(quality_ratio * low - electricity, 2),
            round(quality_ratio * high - electricity, 2),
        ],
        "max_nonenergy_cost_for_equal_cost_per_useful_success_usd_per_day": [
            round((quality_ratio * low - electricity) / DAYS, 2),
            round((quality_ratio * high - electricity) / DAYS, 2),
        ],
        "assumptions": (
            "Only the token count and API proxy range are reported for this exact "
            "window; normal daily energy is an approximation. Both systems are "
            "hypothetically compared on identical tasks, same token accounting, "
            "and fixed success ratio. If the local-to-API success ratio is 1, "
            "this is a price break-even bound, not a demonstrated saving. "
            "Nonenergy costs include GPU capital/depreciation, staff, support, "
            "network, storage, facilities, maintenance, downtime, and governance. "
            "Negative bounds mean local energy alone exceeds quality-adjusted "
            "API proxy; none of these numbers establish real task quality, "
            "local TCO, or an empirical federation benefit."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tariff", type=float, default=0.12)
    parser.add_argument("--success-ratio", type=float, default=1.0)
    args = parser.parse_args()
    try:
        output = derive(args.tariff, args.success_ratio)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
