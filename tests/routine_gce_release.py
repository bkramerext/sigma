"""Offline safety and restart tests for the unattended routine release controller."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "deploy"))
from release_controller import CheckpointedRelease, ReleaseBlocked, Stage

spec = importlib.util.spec_from_file_location(
    "routine_gce_release", ROOT / "deploy/routine_gce_release.py"
)
assert spec and spec.loader
routine = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = routine
spec.loader.exec_module(routine)

SHA = "a" * 40


class UnattendedReleaseTests(unittest.TestCase):
    def test_complete_is_idempotent_across_restarts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            calls: list[str] = []
            stages = [
                Stage("ci", lambda: calls.append("ci") or {"green": True}, lambda: "retry"),
                Stage("deploy", lambda: calls.append("deploy") or {"sha": SHA}, lambda: "blocked"),
            ]
            first = CheckpointedRelease(Path(tmp) / "state", SHA, stages).run()
            second = CheckpointedRelease(Path(tmp) / "state", SHA, stages).run()
            self.assertEqual(calls, ["ci", "deploy"])
            self.assertEqual(set(first["completed"]), {"ci", "deploy"})
            self.assertEqual(first["completed"], second["completed"])

    def test_interrupted_cutover_blocks_instead_of_repeating(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state"
            events: list[str] = []

            def crash() -> dict:
                events.append("cutover")
                raise RuntimeError("uncertain remote cutover")

            steps = [Stage("guarded-cutover", crash, lambda: "blocked")]
            controller = CheckpointedRelease(path, SHA, steps)
            with self.assertRaisesRegex(ReleaseBlocked, "BLOCKED"):
                controller.run()
            with self.assertRaisesRegex(ReleaseBlocked, "not reconciled"):
                controller.run()
            self.assertEqual(events, ["cutover"])
            stored = json.loads((path / f"{SHA}.json").read_text())
            self.assertEqual(stored["active"], "guarded-cutover")

    def test_successful_remote_reconciliation_advances(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state"
            attempts = 0

            def interrupted() -> dict:
                nonlocal attempts
                attempts += 1
                raise RuntimeError("response lost")

            first = Stage("deploy", interrupted, lambda: "done")
            controller = CheckpointedRelease(path, SHA, [first])
            with self.assertRaises(ReleaseBlocked):
                controller.run()
            result = controller.run()
            self.assertEqual(attempts, 1)
            self.assertTrue(result["completed"]["deploy"]["reconciled"])

    def test_failed_readonly_stage_can_retry_without_repeating_completed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state"
            calls: list[str] = []

            def transient() -> dict:
                calls.append("ci")
                if calls.count("ci") == 1:
                    raise RuntimeError("temporary GitHub outage")
                return {"checked": True}

            steps = [
                Stage("evidence", lambda: calls.append("evidence") or {}, lambda: "retry"),
                Stage("ci", transient, lambda: "retry"),
            ]
            controller = CheckpointedRelease(path, SHA, steps)
            with self.assertRaises(ReleaseBlocked):
                controller.run()
            controller.run()
            self.assertEqual(calls, ["evidence", "ci", "ci"])

    def test_checkpoint_plan_change_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state"
            CheckpointedRelease(path, SHA, [Stage("one", lambda: {}, lambda: "retry")]).run()
            with self.assertRaisesRegex(ReleaseBlocked, "step plan"):
                CheckpointedRelease(
                    path, SHA, [Stage("two", lambda: {}, lambda: "retry")]
                ).run()

    def test_symlinked_state_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "state").symlink_to(root / "real", target_is_directory=True)
            with self.assertRaisesRegex(ReleaseBlocked, "symlink"):
                CheckpointedRelease(
                    root / "state", SHA, [Stage("ci", lambda: {}, lambda: "retry")]
                ).run()

    def test_evidence_is_sha_bound_recent_and_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "evidence.json"
            record = {
                "release_sha": SHA,
                "checked_at": datetime.now(UTC).isoformat(),
                "billing_enabled": True,
                "quota_available": True,
                "max_incremental_cost_usd": 12.00,
                "schema_compatible": True,
                "billing_evidence": "verified published rate and current quota report",
                "schema_evidence": "reviewed compatibility test for selected SHA",
            }
            path.write_text(json.dumps(record))
            self.assertEqual(
                routine.assert_safety_evidence(path, SHA)["max_incremental_cost_usd"], 12.00
            )
            for key, bad in [
                ("release_sha", "b" * 40),
                ("max_incremental_cost_usd", 26),
                ("billing_enabled", False),
                ("schema_compatible", False),
                ("checked_at", (datetime.now(UTC) - timedelta(days=2)).isoformat()),
            ]:
                changed = record | {key: bad}
                path.write_text(json.dumps(changed))
                with self.subTest(key=key), self.assertRaises(ReleaseBlocked):
                    routine.assert_safety_evidence(path, SHA)

    def test_release_resource_names_are_fixed_and_scoped(self) -> None:
        release = routine.GceRelease(SHA, Path("evidence.json"))
        self.assertTrue(release.snapshot.startswith("sigma-state-v021-pre-"))
        self.assertTrue(release.disk.startswith("sigma-state-restore-"))
        self.assertTrue(release.vm.startswith("sigma-v021-recovery-"))
        stages = [s.name for s in release.stages()]
        self.assertLess(stages.index("exact-sha-ci"), stages.index("fresh-snapshot"))
        self.assertLess(stages.index("isolated-readonly-restore"), stages.index("guarded-cutover"))
        self.assertLess(stages.index("temporary-resource-cleanup"), stages.index("guarded-cutover"))


if __name__ == "__main__":
    unittest.main()
