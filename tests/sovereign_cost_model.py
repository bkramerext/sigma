"""Offline regression checks for the independent sovereign AI economics model."""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sovereign_cost_model.py"
SPEC = importlib.util.spec_from_file_location("sovereign_cost_model", SCRIPT)
assert SPEC and SPEC.loader
model = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(model)


def scenario():
    return {
        "provenance": "synthetic",
        "source_notes": "Test assumptions are invented.",
        "active_researchers": 10,
        "routes": {
            "campus": {
                "fixed_costs_usd": {"depreciation": 100, "staff": 50},
                "sunk_costs_usd": {"depreciation": 70},
                "capacity_tasks_month": 200,
                "input_usd_per_million": 0,
                "output_usd_per_million": 0,
                "variable_usd_per_task": 0.1,
            },
            "frontier": {
                "fixed_costs_usd": {}, "sunk_costs_usd": {},
                "capacity_tasks_month": 1000,
                "input_usd_per_million": 2,
                "output_usd_per_million": 8,
                "variable_usd_per_task": 0,
            },
        },
        "workloads": [{
            "name": "open", "monthly_tasks": 100,
            "approved_routes": ["campus", "frontier"],
            "input_tokens_per_attempt": 1000,
            "output_tokens_per_attempt": 1000,
            "charged_attempts_per_task": 2,
            "task_success_rate": {"campus": 0.5, "frontier": 0.8},
        }],
        "plans": [{
            "name": "hybrid",
            "enabled_routes": ["campus", "frontier"],
            "external_billing_routes": ["frontier"],
            "external_spend_cap_usd": 10,
            "fixed_costs_usd": {"governance": 20},
            "sunk_costs_usd": {},
            "allocations": {"open": {"campus": 0.6, "frontier": 0.3}},
        }],
    }


class SovereignCostModelTests(unittest.TestCase):
    def test_full_incremental_and_usefulness(self):
        out = model.evaluate(scenario())["plans"][0]
        self.assertTrue(out["feasible"])
        self.assertEqual(out["expected_served_tasks"], 90)
        self.assertEqual(out["expected_unserved_tasks"], 10)
        self.assertEqual(out["expected_successful_useful_tasks"], 54)
        self.assertEqual(out["full_monthly_usd"], 176.6)
        self.assertEqual(out["incremental_monthly_usd"], 106.6)
        self.assertEqual(out["external_billed_usd"], 0.6)

    def test_policy_no_illegal_cloud_escape(self):
        data = scenario()
        data["workloads"][0]["approved_routes"] = ["campus"]
        self.assertFalse(model.evaluate(data)["plans"][0]["feasible"])
        self.assertIn("policy", model.evaluate(data)["plans"][0]["constraint_violations"][0])

    def test_spending_limit(self):
        data = scenario()
        data["plans"][0]["external_spend_cap_usd"] = 0.2
        self.assertFalse(model.evaluate(data)["plans"][0]["feasible"])

    def test_capacity_limit(self):
        data = scenario()
        data["routes"]["campus"]["capacity_tasks_month"] = 50
        self.assertFalse(model.evaluate(data)["plans"][0]["feasible"])

    def test_allocation_conservation(self):
        data = scenario()
        data["plans"][0]["allocations"]["open"]["frontier"] = 0.8
        with self.assertRaises(model.ScenarioError):
            model.evaluate(data)

    def test_sunk_subset_of_fixed(self):
        data = scenario()
        data["routes"]["campus"]["sunk_costs_usd"]["staff"] = 60
        with self.assertRaises(model.ScenarioError):
            model.evaluate(data)

    def test_nonfinite_rejected(self):
        data = scenario()
        data["workloads"][0]["charged_attempts_per_task"] = float("nan")
        with self.assertRaises(model.ScenarioError):
            model.evaluate(data)

    def test_no_success_nulls_unit_cost(self):
        data = scenario()
        data["workloads"][0]["task_success_rate"] = {"campus": 0, "frontier": 0}
        self.assertIsNone(model.evaluate(data)["plans"][0]["full_usd_per_success"])

    def test_distinct_cached_input_rate(self):
        data = scenario()
        data["routes"]["frontier"]["cached_input_usd_per_million"] = 0.2
        data["workloads"][0]["cached_input_tokens_per_attempt"] = 800
        self.assertEqual(model.evaluate(data)["plans"][0]["external_billed_usd"], 0.5136)
        data["workloads"][0]["cached_input_tokens_per_attempt"] = 1001
        with self.assertRaises(model.ScenarioError):
            model.evaluate(data)

    def test_worst_call_budget_risk_is_flagged(self):
        data = scenario()
        data["workloads"][0]["max_charged_attempts_per_task"] = 50
        data["plans"][0]["external_spend_cap_usd"] = 1.0
        result = model.evaluate(data)["plans"][0]
        self.assertTrue(result["feasible"])
        self.assertTrue(result["external_budget_tail_risk"])
        data["workloads"][0]["max_charged_attempts_per_task"] = 1
        with self.assertRaises(model.ScenarioError):
            model.evaluate(data)

    def test_gpu_hours_not_raw_task_count(self):
        data = scenario()
        data["routes"]["campus"]["capacity_units_month"] = 100
        data["routes"]["campus"]["capacity_unit_name"] = "gpu-hour"
        data["workloads"][0]["capacity_units_per_task"] = {"campus": 2.5}
        result = model.evaluate(data)["plans"][0]
        self.assertFalse(result["feasible"])
        self.assertEqual(result["route_capacity_units_used"]["campus"], 150)
        data["workloads"][0].pop("capacity_units_per_task")
        with self.assertRaises(model.ScenarioError):
            model.evaluate(data)

    def test_coverage_infeasibility(self):
        data = scenario()
        data["plans"][0]["minimum_served_fraction"] = .95
        self.assertFalse(model.evaluate(data)["plans"][0]["feasible"])

    def test_duplicate_plan_rejected(self):
        data = scenario()
        data["plans"].append(dict(data["plans"][0]))
        with self.assertRaises(model.ScenarioError):
            model.evaluate(data)

    def test_full_synthetic_scenario_is_deterministic(self):
        data = json.loads(
            (ROOT / "research" / "sovereign_scenario_hypothetical.json").read_text()
        )
        out = model.evaluate(data)
        plans = {p["name"]: p for p in out["plans"]}
        self.assertTrue(plans["campus_local_only"]["feasible"])
        self.assertFalse(plans["frontier_api_only"]["feasible"])
        self.assertAlmostEqual(
            plans["campus_plus_approved_frontier"]["full_monthly_usd"], 19396.69
        )
        self.assertAlmostEqual(
            plans["cross_campus_federation_plus_frontier"]["full_monthly_usd"], 22831.47
        )


if __name__ == "__main__":
    unittest.main()
