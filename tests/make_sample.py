Warning: truncated output (original token count: 3435)
Total output lines: 310

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

    creden…2435 tokens truncated…t len(inspect_project(opened.path).project.strategies) == 3
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
