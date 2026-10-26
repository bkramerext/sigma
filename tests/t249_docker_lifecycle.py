"""Real Docker execution and restart/import persistence for T249 JSON projects.

This script intentionally uses the installed SIGMA sandbox image. No providers,
network requests, or existing projects are touched.
"""
import asyncio
import json
import tempfile
from pathlib import Path

from sigma.project_bundle import import_bundle, read_bundle
from sigma.projects import create_json_project, export_complete_project
from sigma.python_sandbox import execute_research_code, get_execution, list_executions, get_execution_artifact


async def verify():
    with tempfile.TemporaryDirectory(prefix="sigma-t249-docker-") as temporary:
        root = Path(temporary)
        import sigma.projects as projects
        original_root = projects.projects_root
        projects.projects_root = lambda: root
        try:
            project = create_json_project("T249 Docker verification", "Validate durable sandbox execution")
            path = Path(project.path)
            source = "print('T249_DOCKER_EXECUTION_OK')"
            first = await execute_research_code(path, source)
            assert first["status"] == "completed", first
            assert first["exit_code"] == 0, first
            assert "T249_DOCKER_EXECUTION_OK" in first["stdout"], first
            saved = get_execution(path, first["id"])
            assert saved["status"] == "completed" and saved["stdout"] == first["stdout"]
            assert any(item["id"] == first["id"] for item in list_executions(path))
            assert "research-executions/" + first["id"] + ".json" in read_bundle(path)["files"]
            print("PASS real Docker execution and JSON-backed record persistence")

            exported = json.loads(export_complete_project(path))
            imported = root / "imported.json"
            import_bundle(exported, imported)
            assert get_execution(imported, first["id"])["stdout"] == first["stdout"]
            assert any(item["id"] == first["id"] for item in list_executions(imported))
            print("PASS export/import execution persistence")

            # Deliberately leave a running reservation with no live lock to
            # simulate process termination before finalization.
            import sigma.python_sandbox as sandbox
            from uuid import uuid4
            from datetime import datetime, timezone
            from hashlib import sha256
            interrupted = dict(first)
            interrupted["id"] = str(uuid4())
            interrupted["source"] = "print('interrupted')"
            interrupted["source_sha256"] = sha256(interrupted["source"].encode()).hexdigest()
            interrupted["created_at"] = datetime.now(timezone.utc).isoformat()
            interrupted["status"] = "running"
            interrupted["exit_code"] = None
            interrupted["stdout"] = ""
            interrupted["stderr"] = ""
            interrupted["duration_ms"] = None
            interrupted.pop("finished_at", None)
            interrupted["artifacts"] = []
            directory = sandbox._execution_directory(path)
            sandbox._save_record(directory, interrupted)
            observed = get_execution(path, interrupted["id"])
            assert observed["status"] == "interrupted", observed
            assert any(item["id"] == interrupted["id"] and item["status"] == "interrupted"
                       for item in list_executions(path))
            print("PASS interrupted reservation remains inspectable after lock loss")
        finally:
            projects.projects_root = original_root


if __name__ == "__main__":
    asyncio.run(verify())
