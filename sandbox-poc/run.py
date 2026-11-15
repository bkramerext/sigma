"""Standalone proof of concept for isolated SIGMA research code execution."""

from __future__ import annotations

import argparse
import os
import secrets
import selectors
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

IMAGE = "sigma-research-python:0.1"
MAX_SOURCE_BYTES = 16_000
MAX_OUTPUT_BYTES = 32_000


def command(runtime: str = "docker", cidfile: str | None = None) -> list[str]:
    result = [
        runtime,
        "run",
        "--rm",
        "--interactive",
        "--pull=never",
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
        "--env=MPLCONFIGDIR=/tmp/matplotlib",
    ]
    if cidfile:
        result.append(f"--cidfile={cidfile}")
    result.append(IMAGE)
    return result


def execute(source: str, timeout: int = 15, runtime: str = "docker") -> tuple[int, str]:
    encoded = source.encode("utf-8")
    if not encoded or len(encoded) > MAX_SOURCE_BYTES:
        raise ValueError(f"Research source must be 1–{MAX_SOURCE_BYTES} UTF-8 bytes")
    if not 1 <= timeout <= 15:
        raise ValueError("Execution timeout must be 1–15 seconds")
    fd, cid_name = tempfile.mkstemp(prefix="sigma-poc-", suffix=".cid")
    os.close(fd)
    cidfile = cid_name
    os.unlink(cidfile)
    token = secrets.token_hex(16)
    try:
        process = subprocess.Popen(
            command(runtime, cidfile),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            start_new_session=True,
        )
    except FileNotFoundError:
        return 127, "Container runtime is unavailable."
    assert process.stdin and process.stdout and process.stderr
    try:
        process.stdin.write(
            str(len(encoded)).encode("ascii") + b"\n" + encoded + token.encode("ascii") + b"\n"
        )
    except BrokenPipeError:
        pass
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    captured = {"stdout": bytearray(), "stderr": bytearray()}
    marker = b"\x1eSIGMA_DONE:" + token.encode("ascii") + b"\x1f\n"
    stdout_pending = bytearray()
    finished = False
    started = time.monotonic()
    status = 0

    def terminate() -> None:
        try:
            identifier = Path(cidfile).read_text(encoding="ascii").strip()
        except (OSError, UnicodeError):
            identifier = ""
        if len(identifier) == 64 and all(char in "0123456789abcdef" for char in identifier):
            try:
                subprocess.run([runtime, "kill", identifier], timeout=3, check=False)
            except (OSError, subprocess.TimeoutExpired):
                pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        for key in list(selector.get_map().values()):
            selector.unregister(key.fileobj)
            key.fileobj.close()

    while selector.get_map():
        elapsed = time.monotonic() - started
        if elapsed >= timeout:
            status = 124
            terminate()
            break
        for key, _ in selector.select(min(0.1, timeout - elapsed)):
            chunk = os.read(key.fd, MAX_OUTPUT_BYTES + 1)
            if not chunk:
                selector.unregister(key.fileobj)
                continue
            if key.data == "stdout":
                stdout_pending.extend(chunk)
                marker_at = stdout_pending.find(marker)
                if marker_at >= 0:
                    chunk = bytes(stdout_pending[:marker_at])
                    stdout_pending.clear()
                    finished = True
                    try:
                        process.stdin.close()
                    except BrokenPipeError:
                        pass
                else:
                    keep = min(len(marker) - 1, len(stdout_pending))
                    chunk = bytes(stdout_pending[:-keep] if keep else stdout_pending)
                    if keep:
                        del stdout_pending[:-keep]
                    else:
                        stdout_pending.clear()
            current = captured[key.data]
            remaining = MAX_OUTPUT_BYTES - 1 - sum(map(len, captured.values()))
            current.extend(chunk[: max(0, remaining)])
            if len(chunk) > remaining:
                status = 125
                terminate()
                break
        if finished:
            continue
    selector.close()
    process.wait()
    if os.path.exists(cidfile):
        os.unlink(cidfile)
    output = bytes(captured["stdout"] + b"\n" + captured["stderr"])
    if status == 124:
        output = output[: MAX_OUTPUT_BYTES - 28] + b"\nExecution timed out."
    elif status == 125:
        output = output[: MAX_OUTPUT_BYTES - 35] + b"\nExecution output exceeded limit."
    return (status or process.returncode), output.decode("utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", default="docker")
    parser.add_argument("--timeout", type=int, default=15)
    args = parser.parse_args()
    status, output = execute(sys.stdin.read(), args.timeout, args.runtime)
    print(output)
    return 0 if status == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
