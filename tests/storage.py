"""Persistent-disk mode validation, two-owner isolation, restart and full-root restore."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    from sigma import cloud_workspaces, storage

    with patch.dict(
        os.environ,
        {
            "SIGMA_STORAGE_BACKEND": "local",
            "SIGMA_CLOUD_AUTH_ENABLED": "false",
            "SIGMA_CLOUD_AUTH_LOCAL": "true",
        },
        clear=False,
    ):
        assert storage.backend() == "local"
        assert storage.storage_root() is None
        assert not cloud_workspaces.enabled()

    with TemporaryDirectory(prefix="sigma-t100-") as temporary:
        base = Path(temporary)
        base.chmod(0o700)
        root = base / "disk"
        root.mkdir(mode=0o700)
        local_projects = base / "local-projects"
        local_projects.mkdir(mode=0o700)
        original = (ROOT / "samples/nonconsecutive-subset-sums/project.json").read_bytes()
        env = os.environ.copy()
        env.update(
            {
                "SIGMA_STORAGE_BACKEND": "persistent_disk",
                "SIGMA_STORAGE_ROOT": str(root),
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": "https://sigma.test",
                "SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL": "admin@example.test",
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "admin@example.test",
                "GOOGLE_OIDC_CLIENT_ID": "fixture.apps.googleusercontent.com",
                "GOOGLE_OIDC_CLIENT_SECRET": "fixture-secret",
                "SIGMA_CLOUD_OPENAI_API_KEY": "deterministic-no-inference-fixture",
                "SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD": "1.00",
                "SIGMA_CLOUD_USER_SPEND_CEILING_USD": "0.25",
                "SIGMA_CLOUD_USER_MAX_CONCURRENT": "1",
                "SIGMA_CLOUD_GLOBAL_MAX_CONCURRENT": "2",
                "SIGMA_CLOUD_USER_MAX_QUEUED": "2",
                "SIGMA_CLOUD_GLOBAL_MAX_QUEUED": "4",
                "SIGMA_PROJECTS_ROOT": str(local_projects),
                "PYTHONPATH": os.pathsep.join(
                    (str(ROOT / "tests"), str(ROOT / "src"), os.environ.get("PYTHONPATH", ""))
                ),
            }
        )
        test_port = "18088"
        env["SIGMA_CLOUD_PUBLIC_ORIGIN"] = "https://sigma.test"
        command = [
            sys.executable,
            "-m",
            "uvicorn",
            "cloud_workspace_test_app:app",
            "--host",
            "127.0.0.1",
            "--port",
            test_port,
            "--log-level",
            "error",
        ]

        def launch() -> subprocess.Popen:
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.DEVNULL)
            for _ in range(200):
                if process.poll() is not None:
                    raise AssertionError("Persistent-disk API exited during startup")
                try:
                    response = httpx.get(
                        f"http://127.0.0.1:{test_port}/api/ui-instance", timeout=0.1
                    )
                    if response.status_code == 200:
                        return process
                except httpx.HTTPError:
                    pass
                import time

                time.sleep(0.05)
            process.terminate()
            raise AssertionError("Persistent-disk API did not become ready")

        def stop(process: subprocess.Popen) -> None:
            process.terminate()
            process.wait(timeout=10)

        from httpx import Client

        process = launch()
        api = f"http://127.0.0.1:{test_port}"
        headers_a = {"X-Test-Subject": "persistent-subject-a", "X-Test-Email": "a@example.test"}
        headers_b = {"X-Test-Subject": "persistent-subject-b", "X-Test-Email": "b@example.test"}
        try:
            with Client(base_url=api, headers=headers_a) as client_a:
                copied = client_a.post(
                    "/api/projects/samples/open", json={"sample_id": "nonconsecutive-subset-sums"}
                )
                assert copied.status_code == 200, copied.text
                project_path = copied.json()["path"]
                inspected = client_a.get("/api/projects/inspect", params={"path": project_path})
                assert inspected.status_code == 200, inspected.text
                project_view = inspected.json()
                project = project_view["project"]
                from sigma.projects import inspect_project, project_settings

                initial_settings = asdict(project_settings(inspect_project(project_path).project))
                new_settings = {
                    **initial_settings,
                    "title": "T100 Persistent Copy",
                    "problem": "T100 edited project details",
                }
                updated = client_a.post(
                    "/api/projects/update",
                    json={"path": project_path, **new_settings, "expected": initial_settings},
                )
                assert updated.status_code == 200, updated.text
                strategy = client_a.post(
                    "/api/projects/strategies",
                    json={
                        "path": project_path,
                        "title": "T100 persisted strategy",
                        "approach": "Verify private disk persistence.",
                    },
                )
                assert strategy.status_code == 201, strategy.text
                exported = client_a.get("/api/projects/export", params={"path": project_path})
                assert (
                    exported.status_code == 200 and b"T100 persisted strategy" in exported.content
                )
                recent = client_a.get("/api/projects/recent")
                assert recent.status_code == 200 and project["id"] in recent.text
            with Client(base_url=api, headers=headers_b) as client_b:
                denied = client_b.get("/api/projects/inspect", params={"path": project_path})
                assert denied.status_code == 404, denied.text
                traversal = client_b.get(
                    "/api/projects/inspect",
                    params={
                        "path": str(Path(project_path).parent / ".." / Path(project_path).name)
                    },
                )
                assert traversal.status_code in {400, 404}, traversal.text
            with patch.dict(os.environ, env):
                workspace_a = cloud_workspaces.workspace_for_subject("persistent-subject-a")
                workspace_b = cloud_workspaces.workspace_for_subject("persistent-subject-b")
            stop(process)
            process = launch()
            with Client(base_url=api, headers=headers_a) as client_a:
                reopened = client_a.get("/api/projects/inspect", params={"path": project_path})
                assert reopened.status_code == 200, reopened.text
                reopened_project = reopened.json()["project"]
                assert reopened_project["id"] == project["id"]
                assert reopened_project["title"] == "T100 Persistent Copy"
                strategies = client_a.get("/api/projects/strategies", params={"path": project_path})
                assert (
                    strategies.status_code == 200 and "T100 persisted strategy" in strategies.text
                )
                assert client_a.get("/api/projects/recent").status_code == 200
            with Client(base_url=api, headers=headers_b) as client_b:
                assert (
                    client_b.get("/api/projects/inspect", params={"path": project_path}).status_code
                    == 404
                )
            stop(process)
            process = None

            restored = base / "restored-disk"
            shutil.copytree(root, restored)
            restored.chmod(0o700)
            for directory in restored.rglob("*"):
                if directory.is_dir():
                    directory.chmod(0o700)
                elif directory.is_file():
                    directory.chmod(0o600)
            env["SIGMA_STORAGE_ROOT"] = str(restored)
            process = launch()
            with Client(base_url=api, headers=headers_a) as client_a:
                restored_recent = client_a.get("/api/projects/recent")
                assert restored_recent.status_code == 200
                restored_path = restored_recent.json()["projects"][0]["path"]
                assert (
                    Path(restored_path)
                    .resolve()
                    .is_relative_to((restored / "workspaces" / workspace_a.workspace_id).resolve())
                ), f"restored Recent path was not rebased: {restored_path}"
                restored_open = client_a.get(
                    "/api/projects/inspect", params={"path": restored_path}
                )
                assert restored_open.status_code == 200, restored_open.text
                assert restored_open.json()["project"]["id"] == project["id"]
                with patch.dict(os.environ, env):
                    restored_workspace_a = cloud_workspaces.workspace_for_subject(
                        "persistent-subject-a"
                    )
                    restored_workspace_b = cloud_workspaces.workspace_for_subject(
                        "persistent-subject-b"
                    )
                assert restored_workspace_a.workspace_id == workspace_a.workspace_id
                assert restored_workspace_b.workspace_id == workspace_b.workspace_id
                assert (
                    restored_workspace_a.path
                    == (restored / "workspaces" / workspace_a.workspace_id).resolve()
                )
            with Client(base_url=api, headers=headers_b) as client_b:
                assert (
                    client_b.get(
                        "/api/projects/inspect", params={"path": restored_path}
                    ).status_code
                    == 404
                )
            stop(process)
            process = None

            # Unsafe roots and inconsistent roots fail before the API becomes ready.
            env["SIGMA_STORAGE_ROOT"] = str(base / "missing" / "root")
            bad = subprocess.run(
                command,
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=10,
                check=False,
            )
            assert bad.returncode != 0
            workspace_target = base / "workspace-target"
            workspace_target.mkdir(mode=0o700)
            linked_workspace = root / "linked-workspaces"
            linked_workspace.symlink_to(workspace_target, target_is_directory=True)
            env["SIGMA_STORAGE_ROOT"] = str(root)
            env["SIGMA_CLOUD_WORKSPACES_ROOT"] = str(linked_workspace)
            bad = subprocess.run(
                command,
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=10,
                check=False,
            )
            assert bad.returncode != 0
            assert list(workspace_target.iterdir()) == []
            env.pop("SIGMA_CLOUD_WORKSPACES_ROOT", None)
            env["SIGMA_STORAGE_ROOT"] = str(root)
            env["SIGMA_CLOUD_WORKSPACES_ROOT"] = str(base / "outside")
            bad = subprocess.run(
                command,
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=10,
                check=False,
            )
            assert bad.returncode != 0
            env.pop("SIGMA_CLOUD_WORKSPACES_ROOT", None)
            linked = base / "linked-root"
            linked.symlink_to(root)
            env["SIGMA_STORAGE_ROOT"] = str(linked)
            bad = subprocess.run(
                command,
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=10,
                check=False,
            )
            assert bad.returncode != 0
            env["SIGMA_STORAGE_ROOT"] = str(root)
            root.chmod(0o755)
            bad = subprocess.run(
                command,
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=10,
                check=False,
            )
            root.chmod(0o700)
            assert bad.returncode != 0
            env["SIGMA_STORAGE_ROOT"] = str(local_projects)
            env.pop("SIGMA_CLOUD_WORKSPACES_ROOT", None)
            bad = subprocess.run(
                command,
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=10,
                check=False,
            )
            assert bad.returncode != 0
            assert list(local_projects.iterdir()) == []
            assert (
                ROOT / "samples/nonconsecutive-subset-sums/project.json"
            ).read_bytes() == original
            assert list(local_projects.iterdir()) == []
            stub_bin = base / "command-stubs"
            stub_bin.mkdir(mode=0o700)
            docker_log = base / "docker-args"
            (stub_bin / "mountpoint").write_text(
                '#!/bin/sh\n[ "$2" = "$SIGMA_TEST_MOUNTED_PATH" ]\n',
                encoding="utf-8",
            )
            (stub_bin / "docker").write_text(
                f'#!/bin/sh\nprintf "%s\\n" "$@" > "{docker_log}"\n',
                encoding="utf-8",
            )
            (stub_bin / "chown").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            (stub_bin / "sudo").write_text(
                '#!/bin/sh\n[ "$1" = env ] || exit 2\nshift\nexec env "$@"\n',
                encoding="utf-8",
            )
            for stub in stub_bin.iterdir():
                stub.chmod(0o700)
            production_env = os.environ.copy()
            production_env.update(
                {
                    "PATH": str(stub_bin) + os.pathsep + os.environ["PATH"],
                    "SIGMA_TEST_MOUNTED_PATH": str(base / "mounted-state"),
                }
            )
            production_command = [
                str(stub_bin / "sudo"),
                "env",
                "SIGMA_DEPLOY_ENV_FILE=/etc/sigma/deploy.env",
                f"SIGMA_STATE_DISK_MOUNT={base / 'not-mounted'}",
                str(ROOT / "deploy/start-gce.sh"),
            ]
            missing_mount = subprocess.run(
                production_command,
                cwd=ROOT,
                env=production_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=10,
                check=False,
            )
            assert missing_mount.returncode != 0
            assert "not mounted" in missing_mount.stdout
            assert not docker_log.exists(), "Compose launched without the state disk"

            mounted = base / "mounted-state"
            mounted.mkdir(mode=0o700)
            production_command[3] = f"SIGMA_STATE_DISK_MOUNT={mounted}"
            startup = subprocess.run(
                production_command,
                cwd=ROOT,
                env=production_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=10,
                check=False,
            )
            assert startup.returncode == 0, startup.stdout
            docker_args = docker_log.read_text(encoding="utf-8").splitlines()
            assert docker_args[docker_args.index("--env-file") + 1] == "/etc/sigma/deploy.env"
            assert docker_args[-2:] == ["up", "-d"]
            corrupted = base / "corrupted-disk"
            shutil.copytree(root, corrupted)
            corrupted.chmod(0o700)
            mapping = corrupted / "workspaces" / "workspaces.sqlite3"
            mapping.write_bytes(b"not a sqlite database")
            mapping.chmod(0o600)
            env["SIGMA_STORAGE_ROOT"] = str(corrupted)
            process = launch()
            with httpx.Client(
                base_url=f"http://127.0.0.1:{test_port}", headers=headers_a
            ) as client:
                fail_closed = client.get("/api/projects/recent")
                assert fail_closed.status_code == 503, fail_closed.text
            stop(process)
            process = None
            env["SIGMA_STORAGE_ROOT"] = str(root)
            deep_env = os.environ.copy()
            deep_env.pop("SIGMA_STORAGE_BACKEND", None)
            deep_env.pop("SIGMA_STORAGE_ROOT", None)
            deep_env.pop("SIGMA_CLOUD_WORKSPACES_ROOT", None)
            deep_env["SIGMA_T100_PERSISTENT_DISK"] = "1"
            deep = subprocess.run(
                [sys.executable, "tests/cloud_workspaces.py"],
                cwd=ROOT,
                env=deep_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=120,
                check=False,
            )
            assert deep.returncode == 0, deep.stdout
            print(deep.stdout.strip())
            research_env = deep_env.copy()
            research = subprocess.run(
                [sys.executable, "tests/cloud_research.py"],
                cwd=ROOT,
                env=research_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=120,
                check=False,
            )
            assert research.returncode == 0, research.stdout
            print(research.stdout.strip())
        finally:
            if process is not None:
                stop(process)
        print(
            "PASS persistent_disk: two-subject project/recent/export isolation, backend restart, "
            "relocated-root Recent/ownership preservation, full-root backup/restore, fail-closed "
            "roots and GCE startup, unchanged stock sample and LOCAL project directory"
        )


if __name__ == "__main__":
    main()
