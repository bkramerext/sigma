"""Offline, assumption-explicit cost/quality analysis for sovereign AI routing.

This calculator is NOT a policy enforcement engine or an empirical result.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


class ScenarioError(ValueError):
    """Reject unsupported or incomplete scenario inputs."""


def number(value: Any, name: str, *, max_value: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ScenarioError(f"{name}: expected a number")
    result = float(value)
    if not math.isfinite(result) or result < 0 or (max_value is not None and result > max_value):
        raise ScenarioError(f"{name}: nonfinite, negative, or above bound")
    return result


def costs(item: dict[str, Any], label: str) -> tuple[float, float]:
    fixed = item.get("fixed_costs_usd", {})
    sunk = item.get("sunk_costs_usd", {})
    if not isinstance(fixed, dict) or not isinstance(sunk, dict):
        raise ScenarioError(f"{label}: costs must be dictionaries")
    full = sum(number(v, f"{label}.{k}") for k, v in fixed.items())
    sunk_total = 0.0
    for key, value in sunk.items():
        if key not in fixed:
            raise ScenarioError(f"{label}: sunk cost has no corresponding fixed cost")
        portion = number(value, f"{label}.sunk.{key}")
        if portion > number(fixed[key], f"{label}.fixed.{key}"):
            raise ScenarioError(f"{label}: sunk cost exceeds fixed component")
        sunk_total += portion
    return full, sunk_total


def evaluate(data: dict[str, Any]) -> dict[str, Any]:
    """Evaluate explicit allocations, fail feasibility for unapproved data routes."""
    if not isinstance(data, dict):
        raise ScenarioError("scenario must be an object")
    provenance = data.get("provenance")
    if provenance not in ("synthetic", "measured"):
        raise ScenarioError("explicit synthetic/measured provenance required")
    notes = data.get("source_notes")
    if not isinstance(notes, str) or not notes.strip():
        raise ScenarioError("source_notes must document assumptions and sources")
    researchers = number(data.get("active_researchers"), "active_researchers")
    if researchers == 0:
        raise ScenarioError("active_researchers must be positive")
    routes, workloads, plans = (data.get("routes"), data.get("workloads"), data.get("plans"))
    if not isinstance(routes, dict) or not routes:
        raise ScenarioError("nonempty routes object required")
    if not isinstance(workloads, list) or not workloads:
        raise ScenarioError("nonempty workloads list required")
    if not isinstance(plans, list) or not plans:
        raise ScenarioError("nonempty plans list required")

    fixed_by_route: dict[str, tuple[float, float]] = {}
    capacity: dict[str, float] = {}
    units: dict[str, str] = {}
    for route_name, route in routes.items():
        if not isinstance(route_name, str) or not isinstance(route, dict):
            raise ScenarioError("routes require named objects")
        fixed_by_route[route_name] = costs(route, route_name)
        key = "capacity_units_month" if "capacity_units_month" in route else "capacity_tasks_month"
        capacity[route_name] = number(route.get(key), f"{route_name}.{key}")
        unit = route.get("capacity_unit_name", "task")
        if not isinstance(unit, str) or not unit:
            raise ScenarioError("invalid capacity unit name")
        units[route_name] = unit
        for key in ("input_usd_per_million", "output_usd_per_million", "variable_usd_per_task"):
            number(route.get(key), f"{route_name}.{key}")
        for key in ("cached_input_usd_per_million", "variable_usd_per_capacity_unit"):
            if key in route:
                number(route[key], f"{route_name}.{key}")

    by_name: dict[str, dict[str, Any]] = {}
    for work in workloads:
        if not isinstance(work, dict) or not isinstance(work.get("name"), str):
            raise ScenarioError("each workload must have a name")
        name = work["name"]
        if name in by_name:
            raise ScenarioError(f"duplicate workload {name}")
        for key in (
            "monthly_tasks",
            "input_tokens_per_attempt",
            "output_tokens_per_attempt",
            "charged_attempts_per_task",
        ):
            number(work.get(key), f"{name}.{key}")
        cached = number(work.get("cached_input_tokens_per_attempt", 0), f"{name}.cached")
        if cached > work["input_tokens_per_attempt"]:
            raise ScenarioError(f"{name}: cached tokens exceed total input tokens")
        maximum = number(
            work.get("max_charged_attempts_per_task", work["charged_attempts_per_task"]),
            f"{name}.max_charged_attempts_per_task",
        )
        if maximum < work["charged_attempts_per_task"]:
            raise ScenarioError(f"{name}: max charged calls below expected calls")
        approved = work.get("approved_routes")
        quality = work.get("task_success_rate")
        capacity_per = work.get("capacity_units_per_task", {})
        if not isinstance(approved, list) or not set(approved) <= set(routes):
            raise ScenarioError(f"{name}: invalid approved route list")
        if not isinstance(quality, dict) or not set(quality) <= set(routes):
            raise ScenarioError(f"{name}: invalid quality entries")
        if not isinstance(capacity_per, dict) or not set(capacity_per) <= set(routes):
            raise ScenarioError(f"{name}: invalid capacity entries")
        for route_name in approved:
            number(quality.get(route_name), f"{name}.{route_name}.quality", max_value=1)
            if "capacity_units_month" in routes[route_name]:
                number(capacity_per.get(route_name), f"{name}.{route_name}.capacity_per_task")
        by_name[name] = work

    names = [p.get("name") if isinstance(p, dict) else None for p in plans]
    if len(set(names)) != len(names) or None in names:
        raise ScenarioError("plans must have unique names")
    demand = sum(float(w["monthly_tasks"]) for w in workloads)
    results = []
    for plan in plans:
        name = plan["name"]
        enabled = plan.get("enabled_routes")
        external = plan.get("external_billing_routes", [])
        allocations = plan.get("allocations")
        if not isinstance(enabled, list) or not set(enabled) <= set(routes):
            raise ScenarioError(f"{name}: invalid enabled routes")
        if not isinstance(external, list) or not set(external) <= set(enabled):
            raise ScenarioError(f"{name}: invalid billed routes")
        if not isinstance(allocations, dict) or not set(allocations) <= set(by_name):
            raise ScenarioError(f"{name}: invalid allocations")
        overhead, sunk_overhead = costs(plan, f"plan.{name}")
        cap = number(plan.get("external_spend_cap_usd"), f"{name}.external_cap")
        min_coverage = number(
            plan.get("minimum_served_fraction", 0), f"{name}.minimum_served_fraction", max_value=1
        )
        fixed = overhead + sum(fixed_by_route[r][0] for r in enabled)
        sunk = sunk_overhead + sum(fixed_by_route[r][1] for r in enabled)
        usage = {r: 0.0 for r in enabled}
        served = successful = variable = billed = billed_max = 0.0
        violations: list[str] = []

        for workload_name, work in by_name.items():
            allocation = allocations.get(workload_name, {})
            if not isinstance(allocation, dict) or not set(allocation) <= set(enabled):
                raise ScenarioError(f"{name}/{workload_name}: invalid routing allocation")
            fractions = {
                r: number(f, f"{name}.{workload_name}.{r}", max_value=1)
                for r, f in allocation.items()
            }
            if sum(fractions.values()) > 1 + 1e-9:
                raise ScenarioError(f"{name}/{workload_name}: overallocated")
            for route_name, fraction in fractions.items():
                if fraction > 0 and route_name not in work["approved_routes"]:
                    violations.append(f"policy: {workload_name} may not use {route_name}")
                routed = work["monthly_tasks"] * fraction
                served += routed
                successful += routed * work["task_success_rate"].get(route_name, 0)
                route = routes[route_name]
                unit_per = work.get("capacity_units_per_task", {}).get(route_name, 1)
                usage[route_name] += routed * unit_per
                input_tokens = work["input_tokens_per_attempt"]
                cached_tokens = work.get("cached_input_tokens_per_attempt", 0)
                per_call = (
                    (input_tokens - cached_tokens) * route["input_usd_per_million"]
                    + cached_tokens
                    * route.get("cached_input_usd_per_million", route["input_usd_per_million"])
                    + work["output_tokens_per_attempt"] * route["output_usd_per_million"]
                ) / 1_000_000
                extra = route["variable_usd_per_task"] + unit_per * route.get(
                    "variable_usd_per_capacity_unit", 0
                )
                charge = routed * (per_call * work["charged_attempts_per_task"] + extra)
                variable += charge
                if route_name in external:
                    billed += charge
                    billed_max += routed * (
                        per_call
                        * work.get(
                            "max_charged_attempts_per_task", work["charged_attempts_per_task"]
                        )
                        + extra
                    )

        for route_name, used in usage.items():
            if used > capacity[route_name] + 1e-8:
                violations.append(
                    f"capacity: {route_name}: {used:g} {units[route_name]} "
                    f"required versus {capacity[route_name]:g}"
                )
        if billed > cap + 1e-8:
            violations.append(f"external budget: {billed:.2f} USD exceeds {cap:.2f} USD")
        if demand and served / demand + 1e-9 < min_coverage:
            violations.append(f"coverage: {served / demand:.3f} below minimum {min_coverage:.3f}")
        full = fixed + variable
        incremental = full - sunk
        results.append(
            {
                "name": name,
                "feasible": not violations,
                "constraint_violations": violations,
                "monthly_demand_tasks": demand,
                "expected_served_tasks": round(served, 4),
                "expected_unserved_tasks": round(demand - served, 4),
                "expected_successful_useful_tasks": round(successful, 4),
                "full_monthly_usd": round(full, 2),
                "incremental_monthly_usd": round(incremental, 2),
                "sunk_monthly_usd": round(sunk, 2),
                "external_billed_usd": round(billed, 4),
                "external_max_attempts_usd": round(billed_max, 4),
                "external_budget_tail_risk": billed_max > cap + 1e-8,
                "full_usd_per_success": round(full / successful, 4) if successful else None,
                "incremental_usd_per_success": (
                    round(incremental / successful, 4) if successful else None
                ),
                "full_usd_per_active_researcher": round(full / researchers, 4),
                "route_utilization": {
                    r: round(usage[r] / capacity[r], 4) if capacity[r] else None for r in enabled
                },
                "route_capacity_units_used": {r: round(usage[r], 4) for r in enabled},
                "route_capacity_unit_names": {r: units[r] for r in enabled},
            }
        )

    return {
        "provenance": provenance,
        "source_notes": notes,
        "interpretation": (
            "Deterministic expected scenario values, not observed results. "
            "Policy destination approvals are scenario inputs, not independently "
            "verified. Maximum-attempt billing is a hypothetical bound, not "
            "a guaranteed ceiling. Real deployment needs per-call hard "
            "budget reservations, audit, fairness/queue and quality measurements."
        ),
        "plans": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", type=Path)
    args = parser.parse_args()
    try:
        result = evaluate(json.loads(args.scenario.read_text(encoding="utf-8")))
    except (ScenarioError, ValueError, TypeError, KeyError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
