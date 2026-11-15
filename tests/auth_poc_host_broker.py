"""Offline adversarial tests of the narrow, host-side auth container broker."""

from __future__ import annotations

import importlib.util
import os
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "auth_poc_host_broker", ROOT / "auth-poc/host_broker.py"
)
assert SPEC and SPEC.loader
broker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(broker)

A = "a" * 32
B = "b" * 32
RELEASE = "c" * 40


def main() -> None:
    for invalid in ("", "../etc", "abc", A + "/../../", A.upper(), "0" * 33, "--privileged"):
        try:
            broker.validate_id(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("Untrusted workspace ID was accepted")
    assert broker.compose_args(A, "ps", "-q", "browser")[3] == "sigma-personal-" + A
    assert all(A not in part for part in broker.compose_args(B, "stop"))
    assert len(broker.FILES) == 3
    with tempfile.TemporaryDirectory(prefix="sigma-personal-broker-") as temporary:
        root = Path(temporary)
        root.chmod(0o700)
        gateway_root = root / "gateway"
        gateway_root.mkdir(mode=0o700)
        with patch.dict(
            os.environ,
            {
                "SIGMA_AUTH_BROKER_STATE_ROOT": str(root),
                "SIGMA_AUTH_BROKER_GATEWAY_ROOT": str(gateway_root),
                "SIGMA_RELEASE": RELEASE,
            },
        ):
            with (
                patch.object(broker.os, "geteuid", return_value=0),
                patch.object(broker.os, "chown") as chown,
            ):
                a = broker.prepare_state(A)
                b = broker.prepare_state(B)
                assert a != b
                assert a / "auth/auth-poc" != b / "auth/auth-poc"
                assert stat.S_IMODE((a / "auth/auth-poc").stat().st_mode) == 0o700
                assert chown.call_count == 2
            assert broker.compose_env(A)["SIGMA_STATE_DISK_MOUNT"] == str(root / A)
            assert broker.compose_env(B)["SIGMA_STATE_DISK_MOUNT"] == str(root / B)
            # An attacker cannot replace an existing account's state with a link.
            (a / "auth/auth-poc").rmdir()
            (a / "auth/auth-poc").symlink_to(b / "auth/auth-poc")
            try:
                broker.prepare_state(A)
            except (ValueError, OSError):
                pass
            else:
                raise AssertionError("Symlinked credential volume was accepted")
            (a / "auth/auth-poc").unlink()
            with (
                patch.object(broker.os, "geteuid", return_value=0),
                patch.object(broker.os, "chown"),
            ):
                calls: list[list[str]] = []

                def fake_run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
                    calls.append(argv)
                    assert kwargs["env"]["SIGMA_AUTH_POC_WORKSPACE_ID"] in (A, B)
                    assert kwargs["env"]["SIGMA_RELEASE"] == RELEASE
                    assert not any(part == "--privileged" for part in argv)
                    output = (
                        "d" * 64
                        if argv[-3:] == ["ps", "-q", "browser"]
                        else "healthy"
                        if argv[-2:] == ["{{.State.Health.Status}}", "d" * 64]
                        else ""
                    )
                    return subprocess.CompletedProcess(argv, 0, output, "")

                with (
                    patch.object(broker.subprocess, "run", side_effect=fake_run),
                    patch.object(Path, "is_socket", return_value=True),
                ):
                    result = broker.operate("start", A)
                    assert result == {"status": "ready", "worker": "sigma-personal-" + A}
                    assert broker.operate("stop", A)["status"] == "stopped"
                    assert broker.operate("start", B)["status"] == "ready"
                assert all(("--no-build" in c if "up" in c else True) for c in calls)
                assert (a / "auth/auth-poc").is_dir()
                assert (b / "auth/auth-poc").is_dir()
                assert (gateway_root / A).is_dir()
                assert (gateway_root / B).is_dir()
    print(
        "PASS per-subject Docker stack identity, fixed release, symlink rejection and restart safety"
    )


if __name__ == "__main__":
    main()
