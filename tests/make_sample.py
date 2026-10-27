"""End-to-end conversion of an exported project into an editable Samples entry."""

import asyncio
import json
import shutil
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
from research_sessions import (
    REAL_CLIENT,
    execution_tool_fixture,
    investigation,
    provider_response,
    skeptic,
    wait_for,
)

from sigma import agentic_evidence, cli, research_sessions, samples
from sigma.api import export_project_view
from sigma.projects import ProjectError, create_strategy, initialize_project, inspect_project
from sigma.recents import home_projects

MODEL = "gpt-6.1-sol"
PRIVATE_STRINGS = (
    "fixture-secret-token-1234567890",
    "Bearer very-secret-bearer-value-123456",
    "sk-proj-0123456789abcdefghijklmnop",
    "/Users/alice/private-projects/original.sigma",
)


def snapshot_tree(root: Path) -> dict[str, bytes]:
    return {
        str(item.relative_to(root)): item.read_bytes()
        for item in root.rglob("*")
        if item.is_file() and not item.is_symlink()
    }


def rejects(action, message: str) -> None:
    try:
        action()
    except ProjectError as exc:
        assert message in str(exc)
    else:
        raise AssertionError(f"Expected rejection containing {message!r}")


async def create_source_project(root: Path) -> tuple[Path, str, str, str]:
    source = root / "source.sigma"
    view = initialize_project(
        source,
        "Exported research project",
        "Investigate a testable question. Private note: synthetic internal fixture text.",
    )
    first = create_strategy(
        source,
        "Numerical approach",
        "Compute a finite sequence and compare against the recurrence.",
    ).project.strategies[0]
    second = create_strategy(
        source,
        "Structural approach",
        "Prove the recurrence by partitioning objects into disjoint classes.",
    ).project.strategies[1]

    credential = {
        "identity": "fixture-account",
        "mode": "api_key",
        "token": "fixture-secret-token-1234567890",
        "status": "connected",
    }
    config = {"available": True, "model": MODEL, "reasoning_effort": "high"}
    success_outputs = [investigation(1), skeptic(1, "stop", "productive_conclusion")]
    success_outputs[0]["python_code"] = "print(sum(i*i for i in range(5)))"
    success_outputs[0]["evidence_status"] = "Finite numerical check; not a proof."
    execution = {
        "id": str(uuid4()),
        "status": "completed",
        "runtime": "python",
        "source": success_outputs[0]["python_code"],
        "stdout": "30\ncomputation fixture complete",
        "stderr": "",
        "exit_code": 0,
        "duration_ms": 21,
        "artifacts": [],
        "private_config": {"token": PRIVATE_STRINGS[0]},
    }

    async def run_session(strategy_id: str, outputs: list[dict], failed: bool = False):
        async def handler(request):
            assert isinstance(json.loads(request.content), dict)
            if failed:
                return httpx.Response(
                    400,
                    json={"error": {"message": f"Rejected {PRIVATE_STRINGS[0]}"}},
                )
            if not outputs:
                raise AssertionError("Unexpected additional research call")
            return httpx.Response(200, json=provider_response(outputs.pop(0)))

        limits = research_sessions.get_limits(str(source))
        with (
            patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
            patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
            patch.object(
                research_sessions,
                "execution_capabilities",
                return_value=execution_tool_fixture(True),
            ),
            patch(
                "sigma.research_sessions.httpx.AsyncClient",
                side_effect=lambda **kwargs: REAL_CLIENT(
                    transport=httpx.MockTransport(handler), **kwargs
                ),
            ),
            patch.object(
                research_sessions,
                "execute_research_code",
                new=AsyncMock(return_value=execution),
            ),
        ):
            started = await research_sessions.start_session(
                str(source),
                strategy_id,
                str(uuid4()),
                view.project.id,
                credential["identity"],
                expected_limits=limits,
            )
            return await wait_for(source, started["id"])

    successful = await run_session(first.id, success_outputs)
    assert successful["status"] in {"ended", "completed"}
    failed = await run_session(second.id, [], failed=True)
    assert failed["status"] == "failed"

    run_id = uuid4().hex
    agentic_evidence.save(
        source,
        {
            "schema_version": 1,
            "run_id": run_id,
            "project_id": view.project.id,
            "started_at": "2026-10-23T12:00:00+00:00",
            "finished_at": "2026-10-23T12:00:01+00:00",
            "status": "completed",
            "timeline": [{"type": "decision", "message": "Strategy accepted."}],
            "steps": [{"output": {"title": "Generated approach"}}],
            "private_config": {"access_token": PRIVATE_STRINGS[0]},
            "note": PRIVATE_STRINGS[3],
        },
    )
    return source, successful["id"], failed["id"], run_id


async def main() -> None:
    sample_evidence = json.loads(
        Path("samples/nonconsecutive-subset-sums/sample-evidence.json").read_text(encoding="utf-8")
    )
    first_session = next(
        item for item in sample_evidence["research_sessions"] if item["session_number"] == 1
    )
    first_artifact = first_session["artifacts"][0]
    first_outcome = research_sessions._public(first_session)["outcome"]
    assert first_artifact["coordinator_decision"] == "stop_budget_exhausted"
    assert first_artifact["skeptic_output"]["stop_reason"] == "decisive_counterexample"
    assert first_session["outcome"]["label"] == "Mixed · partial progress, unresolved"
    assert first_outcome["assessment"] == "mixed"
    assert first_outcome["label"] == "Mixed · partial progress, unresolved"
    assert first_outcome["solution_review"]["status"] == "partial"
    assert "general recurrence" in " ".join(first_outcome["solution_review"]["proof_obligations"])
    assert "asymptotic limit" in " ".join(first_outcome["solution_review"]["proof_obligations"])
    assert "a_(n+3)=a_(n+2)+a_n" in first_artifact["claim_or_question"]
    assert "a_5=5" in first_artifact["skeptic_response"]
    assert "a_4+a_2=3+1=4" in first_artifact["skeptic_response"]
    assert first_artifact["skeptic_output"]["objections"] == [
        "The proposed three-step recurrence has the explicit n=2 counterexample a_5=5 != a_4+a_2=4."
    ]

    with TemporaryDirectory(prefix="sigma-make-sample-") as temporary:
        root = Path(temporary)
        projects_root = root / "projects"
        catalog = root / "samples"
        state_root = root / "state"
        for directory in (projects_root, catalog, state_root):
            directory.mkdir(mode=0o700)
        with (
            patch.object(samples, "SAMPLES", catalog),
            patch("sigma.projects.projects_root", lambda: projects_root),
            patch("sigma.samples.projects_root", lambda: projects_root),
            patch("sigma.recents.state_directory", lambda: state_root),
        ):
            source, success_id, failed_id, run_id = await create_source_project(projects_root)
            source_before = snapshot_tree(source)
            export = export_project_view(str(source))
            export_file = root / "exported-project.json"
            export_file.write_text(json.dumps(export, ensure_ascii=False), encoding="utf-8")

            with patch.object(
                sys,
                "argv",
                ["sigma", "make_sample", str(export_file), "--name", "t30-exported"],
            ):
                try:
                    cli.main()
                except SystemExit as exit_request:
                    assert exit_request.code == 0
                else:
                    raise AssertionError("make_sample CLI did not return")
            raw_sample = (catalog / "t30-exported" / "project.json").read_text(encoding="utf-8")
            sidecar = (catalog / "t30-exported" / samples.SAMPLE_EVIDENCE).read_text(
                encoding="utf-8"
            )
            for secret in PRIVATE_STRINGS:
                assert secret not in raw_sample and secret not in sidecar
            assert "$SIGMA_SAMPLE_PROJECT_PATH" not in raw_sample
            assert samples.sample_projects()["projects"][0]["id"] == "t30-exported"
            rejects(lambda: samples.make_sample(export_file, "../escape"), "Sample name")
            rejects(lambda: samples.make_sample(export_file, "t30-exported"), "already exists")
            invalid_export = root / "invalid.json"
            invalid_export.write_text('{"export_version": 1}', encoding="utf-8")
            try:
                samples.make_sample(invalid_export, "invalid-export")
            except ProjectError as exc:
                assert "SIGMA project export" in str(exc)
            else:
                raise AssertionError("Unsupported export was accepted")

            opened = samples.open_sample_project("t30-exported")
            assert opened.project.id != export["project"]["id"]
            assert opened.project.title.endswith("v1")
            assert len(opened.project.strategies) == 2
            copied_sessions = research_sessions.list_sessions(opened.path)
            assert len(copied_sessions) == 2
            copied_success = next(
                item for item in copied_sessions if item["status"] in {"ended", "completed"}
            )
            copied_failure = next(item for item in copied_sessions if item["status"] == "failed")
            assert copied_success["id"] not in {success_id, failed_id}
            assert copied_failure["id"] not in {success_id, failed_id}
            by_id = {item["id"]: item for item in copied_sessions}
            success = by_id[copied_success["id"]]
            assert success["status"] in {"ended", "completed"}
            assert copied_failure["status"] == "failed"
            source_outcome = next(
                item["outcome"] for item in export["research_sessions"] if item["id"] == success_id
            )
            assert {
                key: value for key, value in success["outcome"].items() if key != "metrics"
            } == {key: value for key, value in source_outcome.items() if key != "metrics"}
            assert (
                success["outcome"]["metrics"]["sources"]["execution_ids"]
                == source_outcome["metrics"]["sources"]["execution_ids"]
            )
            computational = success["artifacts"][0]["investigator_output"]["python_execution"]
            assert computational["status"] == "completed"
            assert computational["source"] == "print(sum(i*i for i in range(5)))"
            assert computational["stdout"].startswith("30")
            assert success["project_id"] == opened.project.id
            assert success["strategy_id"] in {item.id for item in opened.project.strategies}
            assert agentic_evidence.list_runs(opened.path)[0]["run_id"] == run_id
            assert home_projects()["projects"][0]["id"] == opened.project.id

            create_strategy(
                opened.path,
                "Editable sample strategy",
                "Add a new argument to the copied project.",
            )
            assert len(inspect_project(opened.path).project.strategies) == 3
            assert snapshot_tree(source) == source_before
            assert len(inspect_project(source).project.strategies) == 2

            # Legacy Projects must export a canonical document the same
            # sample-import path can validate; dataclass-only defaults are
            # not fields in a v5 project document.
            legacy_source = projects_root / "legacy-sample-source.sigma"
            legacy_source.mkdir(mode=0o700)
            # Keep an actual v5 stock project as the fixture. Nonconsecutive
            # Subset Sums now carries explicit difficulty metadata in v8.
            legacy_template = Path("samples/jesus-cannabis/project.json")
            legacy_before = legacy_template.read_bytes()
            shutil.copyfile(legacy_template, legacy_source / "project.json")
            legacy_export = export_project_view(str(legacy_source))
            assert legacy_export["project"]["schema_version"] == 5
            assert "ai_model" not in legacy_export["project"]
            assert "reasoning_effort" not in legacy_export["project"]
            legacy_export_path = root / "legacy-export.json"
            legacy_export_path.write_text(
                json.dumps(legacy_export, ensure_ascii=False), encoding="utf-8"
            )
            samples.make_sample(legacy_export_path, "t30-legacy-export")
            legacy_copy = samples.open_sample_project("t30-legacy-export")
            assert legacy_copy.project.problem == legacy_export["project"]["problem"]
            assert [item.title for item in legacy_copy.project.strategies] == [
                item["title"] for item in legacy_export["project"]["strategies"]
            ]
            assert legacy_template.read_bytes() == legacy_before

    print(
        "PASS exported project -> make_sample -> sample loader preserves sessions, outcomes, evidence and provenance safely"
    )


if __name__ == "__main__":
    asyncio.run(main())
