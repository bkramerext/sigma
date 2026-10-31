#!/usr/bin/env python3
"""Optional SciPy sensitivity check for the synthetic Sovereign AI scenario.

This is a fractional linear-programming *upper bound*, not a real router,
an empirical measurement, a data-policy decision engine, or a spending guard.
Run in an environment with scipy installed (not a SIGMA runtime dependency).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scipy.optimize import linprog


def task_cost(route: dict[str, Any], work: dict[str, Any], route_name: str) -> float:
    input_tokens = work["input_tokens_per_attempt"]
    cached = work.get("cached_input_tokens_per_attempt", 0)
    per_call = (
        (input_tokens - cached) * route["input_usd_per_million"]
        + cached * route.get("cached_input_usd_per_million", route["input_usd_per_million"])
        + work["output_tokens_per_attempt"] * route["output_usd_per_million"]
    ) / 1_000_000
    capacity_per_task = work.get("capacity_units_per_task", {}).get(route_name, 1)
    return (
        per_call * work["charged_attempts_per_task"]
        + route["variable_usd_per_task"]
        + capacity_per_task * route.get("variable_usd_per_capacity_unit", 0)
    )


def optimize(
    data: dict[str, Any], plan_name: str, *, external_cap_usd: float | None = None,
    minimum_success: float | None = None,
) -> dict[str, Any]:
    """Optimize full-coverage fractional allocations with explicit constraints.

    A fraction of a task is allowed by the continuous relaxation. Thus the
    result is an optimistic bound for indivisible workloads, not an executable
    routing plan. The objective is max useful successes or min cost at a quality
    floor; it is NOT minimum cost-per-success or joint cost/quality optimization.
    """
    if data.get("provenance") != "synthetic":
        raise ValueError("Only explicitly synthetic scenarios are supported")
    plan = next(p for p in data["plans"] if p["name"] == plan_name)
    routes = data["routes"]
    enabled = set(plan["enabled_routes"])
    billed = set(plan["external_billing_routes"])
    workloads = data["workloads"]
    variables = [
        (work, route_name)
        for work in workloads
        for route_name in routes
        if route_name in enabled and route_name in work["approved_routes"]
    ]
    if any(not any(w is work for w, _ in variables) for work in workloads):
        return {"plan": plan_name, "feasible": False, "reason": "no approved full coverage"}
    variable_costs = [
        task_cost(routes[route_name], work, route_name)
        for work, route_name in variables
    ]
    success_rates = [
        work["task_success_rate"][route_name] for work, route_name in variables
    ]
    fixed = sum(
        sum(routes[r].get("fixed_costs_usd", {}).values()) for r in enabled
    ) + sum(plan.get("fixed_costs_usd", {}).values())
    equalities = [
        [1.0 if w is work else 0.0 for w, _ in variables] for work in workloads
    ]
    demand = [work["monthly_tasks"] for work in workloads]
    inequalities: list[list[float]] = []
    limits: list[float] = []
    for route_name in sorted(enabled):
        route = routes[route_name]
        capacity = route.get("capacity_units_month", route.get("capacity_tasks_month"))
        inequalities.append([
            work.get("capacity_units_per_task", {}).get(route_name, 1)
            if r == route_name else 0.0
            for work, r in variables
        ])
        limits.append(capacity)
    inequalities.append([
        price if r in billed else 0.0
        for price, (_, r) in zip(variable_costs, variables)
    ])
    cap = plan["external_spend_cap_usd"] if external_cap_usd is None else external_cap_usd
    if cap < 0:
        raise ValueError("Negative external budget")
    limits.append(cap)
    if minimum_success is not None:
        inequalities.append([-rate for rate in success_rates])
        limits.append(-minimum_success)
    objective = (
        variable_costs if minimum_success is not None
        else [-rate for rate in success_rates]
    )
    result = linprog(
        objective, A_ub=inequalities, b_ub=limits,
        A_eq=equalities, b_eq=demand,
        bounds=[(0, None)] * len(variables), method="highs",
    )
    if not result.success:
        return {"plan": plan_name, "feasible": False, "reason": result.message}
    successful = sum(float(x) * q for x, q in zip(result.x, success_rates))
    variable_usd = sum(float(x) * p for x, p in zip(result.x, variable_costs))
    billed_usd = sum(
        float(x) * p
        for x, p, (_, r) in zip(result.x, variable_costs, variables)
        if r in billed
    )
    return {
        "plan": plan_name,
        "feasible": True,
        "objective": "minimum cost at quality floor"
        if minimum_success is not None else "maximum expected successes",
        "continuous_relaxation": True,
        "expected_successful_tasks": round(successful, 6),
        "full_monthly_usd": round(fixed + variable_usd, 6),
        "full_usd_per_success": round((fixed + variable_usd) / successful, 6)
        if successful else None,
        "external_billed_usd": round(billed_usd, 6),
        "allocations_tasks": {
            work["name"] + " -> " + route_name: round(float(x), 6)
            for (work, route_name), x in zip(variables, result.x)
            if x > 1e-7
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", type=Path)
    parser.add_argument("--budget", type=float, default=None)
    parser.add_argument("--min-success", type=float, default=None)
    args = parser.parse_args()
    data = json.loads(args.scenario.read_text(encoding="utf-8"))
    print(json.dumps([
        optimize(
            data, plan["name"], external_cap_usd=args.budget,
            minimum_success=args.min_success,
        )
        for plan in data["plans"]
    ], indent=2))


if __name__ == "__main__":
    main()
