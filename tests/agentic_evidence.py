"""Bounded, private per-project evidence storage scenarios."""

import os
import stat
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from sigma.agentic_evidence import (
    DIRECTORY,
    MAX_RECORD_BYTES,
    MAX_TOTAL_BYTES,
    _encoded,
    get_run,
    list_runs,
    save,
)
from sigma.projects import ProjectError, initialize_project


def record(project_id: str, index: int) -> dict:
    return {
        "schema_version": 1,
        "run_id": f"{index:032x}",
        "started_at": f"2026-10-22T00:00:{index:02d}+00:00",
        "finished_at": f"2026-10-22T00:01:{index:02d}+00:00",
        "project_id": project_id,
        "steps": [],
        "history": [],
        "timeline": [],
        "terminal": {"status": "failed", "summary": "Fixture run"},
    }


def main() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        first = root / "first.sigma"
        second = root / "second.sigma"
        one = initialize_project(first, "First", "Question")
        other = initialize_project(second, "Second", "Other question")

        for index in range(33):
            save(first, record(one.project.id, index))
        listed = list_runs(first)
        assert len(listed) == 32
        assert listed[0]["run_id"] == f"{32:032x}"
        assert all(entry["project_id"] == one.project.id for entry in listed)
        exported = get_run(first, f"{32:032x}")
        assert exported["terminal"]["summary"] == "Fixture run"
        try:
            get_run(second, f"{32:032x}")
        except ProjectError as exc:
            assert "not found" in str(exc)
        else:
            raise AssertionError("A run was readable through a different project")

        directory = first / DIRECTORY
        assert stat.S_IMODE(directory.stat().st_mode) == 0o700
        assert stat.S_IMODE((directory / f"{32:032x}.json").stat().st_mode) == 0o600
        try:
            _encoded({**record(one.project.id, 34), "large": "x" * MAX_RECORD_BYTES})
        except ProjectError as exc:
            assert "512 KB" in str(exc)
        else:
            raise AssertionError("Oversized evidence record was accepted")

        unsafe = directory / f"{uuid4().hex}.json"
        unsafe.symlink_to(first / "project.json")
        try:
            list_runs(first)
        except ProjectError as exc:
            assert "unsafe" in str(exc)
        else:
            raise AssertionError("Evidence symlink was followed")
        finally:
            unsafe.unlink(missing_ok=True)

        large_directory = second / DIRECTORY
        large_directory.mkdir(mode=0o700)
        for index in range(100, 131):
            item = {**record(other.project.id, index), "payload": "x" * 271000}
            target = large_directory / f"{index:032x}.json"
            descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(_encoded(item))
        save(second, record(other.project.id, 200))
        assert (
            sum(file.stat().st_size for file in large_directory.glob("*.json")) <= MAX_TOTAL_BYTES
        )
        assert len(list_runs(second)) <= 32
        try:
            get_run(second, f"{100:032x}")
        except ProjectError as exc:
            assert "not found" in str(exc)
        else:
            raise AssertionError("Byte retention limit did not prune an expired run")

    print(
        "PASS evidence persistence, cross-project isolation, private modes, run/byte retention, size cap and symlink rejection"
    )


if __name__ == "__main__":
    main()
