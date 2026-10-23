"""Research code isolation contract and immutable artifact capture."""

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

import test_environment as _test_environment  # noqa: F401
from fastapi.testclient import TestClient

from sigma import python_sandbox, research_sessions
from sigma.api import app
from sigma.projects import ProjectError, create_strategy, initialize_project, project_path


def rejects(action) -> None:
    try:
        action()
    except ProjectError:
        return
    raise AssertionError("Expected invalid research execution request to be rejected")


def main() -> None:
    args = python_sandbox.docker_command()
    joined = " ".join(args)
    for required in (
        "--network=none",
        "--memory=512m",
        "--memory-swap=512m",
        "--cpus=1",
        "--pids-limit=64",
        "--read-only",
        "--tmpfs=/tmp:rw,noexec,nosuid,size=64m",
        "--tmpfs=/artifacts:rw,noexec,nosuid,size=16m",
        "--user=65532:65532",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--pull=never",
        python_sandbox.IMAGE,
    ):
        assert required in joined
    assert not any("mount" in arg or "volume" in arg for arg in args)
    assert python_sandbox.MAX_SOURCE_BYTES == 16_000
    assert python_sandbox.MAX_OUTPUT_BYTES == 32_000
    assert python_sandbox.EXECUTION_TIMEOUT_SECONDS == 15
    assert python_sandbox._EXECUTION_GATE.acquire(blocking=False)
    try:
        assert asyncio.run(python_sandbox.execute("print('busy')")).status == "busy"
    finally:
        python_sandbox._EXECUTION_GATE.release()

    with TemporaryDirectory() as temporary:
        missing_project = Path(temporary) / "missing.sigma"
        rejects(lambda: python_sandbox.list_executions(missing_project))
        assert not missing_project.exists()
        path = Path(temporary) / "p.sigma"
        view = initialize_project(path, "Sandbox project", "Run a finite computation")
        strategy = create_strategy(path, "Sandbox strategy", "Check a finite computation.")
        session_id, strategy_id = str(uuid4()), strategy.project.strategies[0].id
        research_sessions._save(
            str(path),
            {
                "id": session_id,
                "project_path": str(project_path(path)),
                "project_id": view.project.id,
                "status": "running",
                "strategy_runs": [{"strategy_id": strategy_id, "cycle": 2}],
                "steps": [],
                "events": [],
            },
        )
        fake = python_sandbox.ExecutionResult(
            "completed",
            0,
            "2\n",
            "",
            17,
            "sha256:" + "a" * 64,
            (("plot.png", "image/png", b"PNG fixture"),),
        )
        with patch.object(python_sandbox, "execute", return_value=fake):
            record = asyncio.run(
                python_sandbox.execute_research_code(
                    str(path),
                    "print(1 + 1)",
                    session_id=session_id,
                    strategy_id=strategy_id,
                    cycle=2,
                )
            )
        assert record["status"] == "completed" and record["stdout"] == "2\n"
        assert record["session_id"] == session_id and record["strategy_id"] == strategy_id
        assert record["cycle"] == 2 and record["source"] == "print(1 + 1)"
        assert record["environment"]["network"] == "none"
        assert record["environment"]["image_id"] == "sha256:" + "a" * 64
        assert record["artifacts"] == [
            {
                "filename": "plot.png",
                "media_type": "image/png",
                "size_bytes": len(b"PNG fixture"),
                "sha256": __import__("hashlib").sha256(b"PNG fixture").hexdigest(),
            }
        ]
        assert python_sandbox.get_execution(str(path), record["id"]) == record
        assert python_sandbox.get_execution_artifact(str(path), record["id"], "plot.png") == (
            b"PNG fixture",
            "image/png",
        )
        assert python_sandbox.list_executions(str(path)) == [record]
        rejects(lambda: python_sandbox.get_execution(str(path), str(uuid4())))
        rejects(lambda: asyncio.run(python_sandbox.execute_research_code(str(path), "x" * 16_001)))
        rejects(
            lambda: asyncio.run(
                python_sandbox.execute_research_code(str(path), "print(1)", cycle=0)
            )
        )
        rejects(
            lambda: asyncio.run(
                python_sandbox.execute_research_code(str(path), "print(1)", session_id="../x")
            )
        )
        rejects(
            lambda: asyncio.run(
                python_sandbox.execute_research_code(str(path), "print(1)", session_id=session_id)
            )
        )
        rejects(
            lambda: asyncio.run(
                python_sandbox.execute_research_code(
                    str(path),
                    "print(1)",
                    session_id=session_id,
                    strategy_id=str(uuid4()),
                    cycle=2,
                )
            )
        )
        rejects(
            lambda: asyncio.run(
                python_sandbox.execute_research_code(
                    str(path), "print(1)", session_id=session_id, strategy_id=strategy_id, cycle=1
                )
            )
        )
        foreign_session_id = str(uuid4())
        research_sessions._save(
            str(path),
            {
                "id": foreign_session_id,
                "project_path": str(project_path(path)),
                "project_id": str(uuid4()),
                "status": "running",
                "strategy_runs": [{"strategy_id": strategy_id, "cycle": 2}],
                "steps": [],
                "events": [],
            },
        )
        rejects(
            lambda: asyncio.run(
                python_sandbox.execute_research_code(
                    str(path),
                    "print(1)",
                    session_id=foreign_session_id,
                    strategy_id=strategy_id,
                    cycle=2,
                )
            )
        )
        directory = path / "research-executions"
        stored = directory / f"{record['id']}.json"
        assert stored.stat().st_mode & 0o777 == 0o600
        assert directory.stat().st_mode & 0o777 == 0o700
        assert (path / "project.json").exists()

        async def cancellation_is_durable():
            started = asyncio.Event()
            finish = asyncio.Event()

            async def delayed(_source):
                started.set()
                await finish.wait()
                return fake

            with patch.object(python_sandbox, "execute", side_effect=delayed):
                task = asyncio.create_task(
                    python_sandbox.execute_research_code(str(path), "print('durable')")
                )
                await started.wait()
                task.cancel()
                finish.set()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                else:
                    raise AssertionError("Cancellation should propagate after saving the result")

            records = python_sandbox.list_executions(str(path))
            assert any(item["source"] == "print('durable')" for item in records)

        asyncio.run(cancellation_is_durable())

        client = TestClient(app)
        response = client.get("/api/projects/research-executions", params={"path": str(path)})
        assert response.status_code == 200 and any(
            item["id"] == record["id"] for item in response.json()["executions"]
        )
        response = client.get(
            f"/api/projects/research-executions/{record['id']}",
            params={"path": str(path)},
        )
        assert response.status_code == 200 and response.json()["source"] == "print(1 + 1)"
        response = client.get(
            f"/api/projects/research-executions/{record['id']}/artifacts/plot.png",
            params={"path": str(path)},
        )
        assert (
            response.status_code == 200
            and response.content == b"PNG fixture"
            and response.headers["content-disposition"].startswith("attachment;")
        )
        with patch.object(python_sandbox, "execute", return_value=fake):
            response = client.post(
                "/api/projects/research-executions",
                json={"path": str(path), "source": "print(1+1)"},
            )
        assert response.status_code == 201 and response.json()["status"] == "completed"
        invalid = client.post(
            "/api/projects/research-executions",
            json={"path": str(path), "source": "print(1)", "unexpected": "field"},
        )
        assert invalid.status_code == 422

    sample_root = Path(__file__).resolve().parents[1] / "samples"
    with TemporaryDirectory(prefix=".a19-sandbox-check-", dir=sample_root) as temporary:
        sample = Path(temporary) / "sample.sigma"
        initialize_project(sample, "Temporary sample", "Must not receive execution data")
        rejects(lambda: python_sandbox.list_executions(sample))
        assert not (sample / "research-executions").exists()

    print(
        "PASS fixed isolated command, source bounds, project-scoped artifact persistence, metadata validation, and HTTP execution/list API"
    )


if __name__ == "__main__":
    main()
