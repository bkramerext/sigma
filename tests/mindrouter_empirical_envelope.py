"""Deterministic checks for source-derived, explicitly conditional MindRouter bounds."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "mindrouter_empirical_envelope.py"
SPEC = importlib.util.spec_from_file_location("mindrouter_empirical_envelope", SCRIPT)
assert SPEC and SPEC.loader
model = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(model)


class MindRouterEnvelopeTests(unittest.TestCase):
    def test_reported_source_inputs(self):
        self.assertEqual(model.TOKENS, 872_997_430)
        self.assertEqual(model.DAYS, 17)
        self.assertEqual(model.API_EQUIVALENT_USD, (4027.0, 11896.0))
        self.assertEqual(model.APPROX_KWH_PER_DAY, 275)

    def test_energy_normalization(self):
        result = model.derive()
        self.assertEqual(result["approx_energy_kwh_over_window"], 4675)
        self.assertEqual(result["derived_tokens_per_kwh"], 186737.42)
        self.assertEqual(result["derived_wh_per_1000_tokens"], 5.3551)

    def test_electricity_and_api_proxy(self):
        result = model.derive()
        self.assertEqual(result["illustrative_electricity_cost_usd"], 561)
        self.assertEqual(result["electricity_only_usd_per_million_tokens"], 0.6426)
        self.assertEqual(
            result["published_api_equivalent_usd_per_million_tokens"],
            [4.6128, 13.6266],
        )

    def test_equal_quality_break_even(self):
        result = model.derive()
        self.assertEqual(
            result["max_nonenergy_cost_for_equal_cost_per_useful_success_usd_17d"],
            [3466, 11335],
        )
        self.assertEqual(
            result["max_nonenergy_cost_for_equal_cost_per_useful_success_usd_per_day"],
            [203.88, 666.76],
        )

    def test_lower_quality_reduces_affordable_overhead(self):
        result = model.derive(local_to_api_task_success_ratio=0.5)
        self.assertEqual(
            result["max_nonenergy_cost_for_equal_cost_per_useful_success_usd_17d"],
            [1452.5, 5387],
        )

    def test_very_low_quality_can_make_local_noncompetitive_on_energy_alone(self):
        result = model.derive(local_to_api_task_success_ratio=0.1)
        self.assertLess(
            result["max_nonenergy_cost_for_equal_cost_per_useful_success_usd_17d"][0], 0
        )

    def test_tariff_sensitivity(self):
        result = model.derive(electricity_usd_per_kwh=0.20)
        self.assertEqual(result["illustrative_electricity_cost_usd"], 935)
        self.assertEqual(
            result["max_nonenergy_cost_for_equal_cost_per_useful_success_usd_17d"],
            [3092, 10961],
        )

    def test_nonfinite_or_negative_inputs_rejected(self):
        for value in (float("nan"), float("inf"), -1, True):
            with self.subTest(value=value):
                with self.assertRaises((TypeError, ValueError)):
                    model.derive(electricity_usd_per_kwh=value)
                with self.assertRaises((TypeError, ValueError)):
                    model.derive(local_to_api_task_success_ratio=value)


if __name__ == "__main__":
    unittest.main()
