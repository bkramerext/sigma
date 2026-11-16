"""Credential-free, fixed-output health probes for private SIGMA containers.

This program MUST NOT inspect credential stores, environment values, Chromium
command lines or HTTP response bodies. Only status codes and a fixed allowlist
of process names/ports are printed for the local SIGMA stdout diagnostics.
"""

from __future__ import annotations

import os
import socket
import stat
import sys
from pathlib import Path


def _tcp(port: int, target: str | None = None) -> str:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1) as conn:
            conn.settimeout(1)
            if target is None:
                return "listening"
            conn.sendall(
                ("GET " + target + " HTTP/1.0\r\n"
                 "Host: 127.0.0.1\r\nConnection: close\r\n\r\n").encode("ascii")
            )
            first = conn.recv(96).split(b"\r\n", 1)[0].split()
            if len(first) >= 2 and first[0] in (b"HTTP/1.0", b"HTTP/1.1"):
                try:
                    code = int(first[1])
                    return "http_" + str(code) if 100 <= code <= 599 else "invalid"
                except ValueError:
                    return "invalid"
            return "invalid"
    except (OSError, TimeoutError):
        return "unreachable"


def _processes() -> dict[str, int]:
    expected = ("chromium", "Xvfb", "x11vnc", "websockify", "uvicorn")
    counts = dict.fromkeys(expected, 0)
    try:
        processes = Path("/proc").iterdir()
        for directory in processes:
            if not directory.name.isdecimal():
                continue
            try:
                name = (directory / "comm").read_text(encoding="ascii").strip()
            except (OSError, UnicodeError):
                continue
            if name in counts:
                counts[name] += 1
    except OSError:
        pass
    return counts


def _limited_number(path: str) -> str:
    try:
        raw = Path(path).read_text(encoding="ascii").strip()
        if raw.isdecimal() and int(raw) <= 10**12:
            return raw
    except (OSError, ValueError):
        pass
    return "unavailable"


def _socket_present(path: str) -> str:
    try:
        return "present" if stat.S_ISSOCK(os.stat(path).st_mode) else "missing"
    except OSError:
        return "missing"


def report(mode: str) -> list[str]:
    if mode not in {"browser", "worker"}:
        raise ValueError("Invalid diagnostic mode")
    counts = _processes()
    lines = ["component=" + mode]
    if mode == "worker":
        lines.append(
            "local_model_gateway_enabled=" + (
                "yes" if os.environ.get("SIGMA_AUTH_POC_LOCAL_DOCKER") == "1" else "no"
            )
        )
    if mode == "browser":
        lines.extend(
            [
                "x11_socket=" + _socket_present("/tmp/.X11-unix/X99"),
                "vnc_password_file=" + (
                    "present" if Path("/tmp/sigma-vnc-pass").is_file() else "missing"
                ),
                "vnc_tcp_5900=" + _tcp(5900),
                "websocket_http_6080=" + _tcp(6080, "/vnc.html"),
                "chromium_processes=" + str(counts["chromium"]),
                "xvfb_processes=" + str(counts["Xvfb"]),
                "x11vnc_processes=" + str(counts["x11vnc"]),
                "websockify_processes=" + str(counts["websockify"]),
            ]
        )
    else:
        lines.extend(
            [
                "oauth_http_8001=" + _tcp(8001, "/health"),
                "model_http_8002=" + _tcp(8002, "/v1/account"),
                "uvicorn_processes=" + str(counts["uvicorn"]),
            ]
        )
    lines.extend(
        [
            "cgroup_memory_bytes=" + _limited_number("/sys/fs/cgroup/memory.current"),
            "cgroup_pids=" + _limited_number("/sys/fs/cgroup/pids.current"),
        ]
    )
    return lines


def browser_healthy() -> bool:
    """Require a live Chromium GUI, not just an HTTP-speaking VNC proxy."""
    status = dict(line.split("=", 1) for line in report("browser"))
    return (
        status["x11_socket"] == "present"
        and status["vnc_tcp_5900"] == "listening"
        and status["websocket_http_6080"] == "http_200"
        # Python-based websockify commonly appears as "python3" in /proc
        # rather than "websockify". Its HTTP listener is authoritative.
        and int(status["chromium_processes"]) > 0
    )


def main() -> None:
    if sys.argv[1:] == ["--health"]:
        raise SystemExit(0 if browser_healthy() else 1)
    if len(sys.argv) != 2 or sys.argv[1] not in {"browser", "worker"}:
        raise SystemExit(2)
    for line in report(sys.argv[1]):
        print(line)


if __name__ == "__main__":
    main()
