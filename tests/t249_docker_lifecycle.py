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

            # Capture actual bytes written by the sandbox into /artifacts.
            artifact_source = (
                "from pathlib import Path\n"
                "Path('/artifacts/proof.bin').write_bytes(bytes(range(256)))\n"
                "print('T249_ARTIFACT_OK')"
            )
            artifact_run = await execute_research_code(path, artifact_source)
            assert artifact_run["status"] == "completed", artifact_run
            assert artifact_run["exit_code"] == 0, artifact_run
            assert any(item["filename"] == "proof.bin" for item in artifact_run["artifacts"]), artifact_run
            artifact_bytes, media_type = get_execution_artifact(path, artifact_run["id"], "proof.bin")
            assert artifact_bytes == bytes(range(256)), (len(artifact_bytes), media_type)
            assert get_execution(path, artifact_run["id"])["artifacts"] == artifact_run["artifacts"]
            print("PASS real Docker binary artifact capture and integrity")

            exported = json.loads(export_complete_project(path))
            imported = root / "imported.json"
            import_bundle(exported, imported)
            assert get_execution(imported, first["id"])["stdout"] == first["stdout"]
            assert get_execution_artifact(imported, artifact_run["id"], "proof.bin")[0] == bytes(range(256))
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

            # An interrupted reservation must survive export/import without
            # being promoted to success or silently executed again.
            recovered = root / "recovered.json"
            import_bundle(json.loads(export_complete_project(path)), recovered)
            recovered_record = get_execution(recovered, interrupted["id"])
            assert recovered_record["status"] == "interrupted", recovered_record
            assert recovered_record["stdout"] == ""
            assert recovered_record["exit_code"] is None
            assert get_execution(path, interrupted["id"])["status"] == "interrupted"
            print("PASS interruption evidence survives export/import")

            # Integrity checks must detect same-length modifications to
            # captured bytes, including after a valid Docker run.
            from sigma.project_bundle import read_file, write_file
            member = f"research-executions/{artifact_run['id']}.artifacts/proof.bin"
            original = read_file(path, member)
            tampered = bytes([original[0] ^ 0xff]) + original[1:]
            write_file(path, member, tampered)
            from sigma.projects import ProjectError
            try:
                get_execution_artifact(path, artifact_run["id"], "proof.bin")
            except ProjectError:
                pass
            else:
                raise AssertionError("Modified binary artifact passed integrity verification")
            write_file(path, member, original)
            assert get_execution_artifact(path, artifact_run["id"], "proof.bin")[0] == original
            print("PASS corrupted artifact rejected without losing valid evidence")

            # Kill a separate SIGMA worker after it has durably reserved an
            # execution. This is a real process death, not a mocked lock loss.
            import os
            import signal
            import subprocess
            import sys
            import time
            child_code = (
                "import asyncio,sys\n"
                "from sigma.python_sandbox import execute_research_code\n"
                "asyncio.run(execute_research_code(sys.argv[1], "
                "'import time; time.sleep(6); print(42)'))\n"
            )
            prior_ids = {item["id"] for item in list_executions(path)}
            child = subprocess.Popen(
                [sys.executable, "-c", child_code, str(path)],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                env=os.environ.copy(),
            )
            killed = False
            try:
                deadline = time.monotonic() + 12
                while time.monotonic() < deadline:
                    current = [item for item in list_executions(path)
                               if item["id"] not in prior_ids and item["status"] == "running"]
                    if current:
                        doomed_id = current[0]["id"]
                        child.kill()
                        child.wait(timeout=5)
                        killed = True
                        break
                    if child.poll() is not None:
                        raise AssertionError(
                            "Docker worker exited before reservation: "
                            + child.stderr.read().decode(errors="replace")
                        )
                    await asyncio.sleep(0.05)
                assert killed, "Docker worker did not create a running reservation"
                dead = get_execution(path, doomed_id)
                assert dead["status"] == "interrupted", dead
                assert dead["exit_code"] is None
                assert get_execution(imported, first["id"])["status"] == "completed"
                print("PASS real SIGMA worker termination preserves uncertain execution")
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=5)


        finally:
            projects.projects_root = original_root


if __name__ == "__main__":
    asyncio.run(verify())
