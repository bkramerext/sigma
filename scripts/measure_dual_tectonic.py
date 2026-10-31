"""Measure two *real* simultaneous Tectonic compilers, without AI/provider calls.

Run inside the same 5 GB / 2 CPU cgroup as the hosted backend (see
.github/workflows/concurrency-capacity.yml). This tests compilation resources,
not live research-provider throughput or the deployed VM's background load.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import tempfile
import time
from pathlib import Path
from subprocess import DEVNULL, Popen

FIXTURE_PAIRS = (
    ("papers/maximum-regions.tex", "papers/nonconsecutive-subset-sums.tex"),
    ("papers/xenopus-tail-regeneration.tex", "papers/operation-narrow-passage.tex"),
)
MAX_TEX_BYTES = 2_000_000
MAX_PDF_BYTES = 20_000_000


def _memory_bytes(name: str) -> int | None:
    try:
        value = Path("/sys/fs/cgroup", name).read_text().strip()
        return int(value) if value != "max" else None
    except (OSError, ValueError):
        return None


def _rss_kib(pid: int) -> int:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    except (OSError, ValueError, IndexError):
        pass
    return 0


def _launch(tex: Path, parent: Path, index: int, executable: str, cache: Path):
    data = tex.read_bytes()
    if len(data) > MAX_TEX_BYTES:
        raise ValueError(f"{tex}: exceeds production TeX source limit")
    directory = parent / f"compiler-{index}"
    directory.mkdir()
    source = directory / "report.tex"
    source.write_bytes(data)
    log = directory / "tectonic.log"
    log_stream = log.open("wb")
    env = {
        "PATH": str(Path(executable).parent),
        "HOME": os.path.expanduser("~"),
        "XDG_CACHE_HOME": str(cache),
        "TECTONIC_UNTRUSTED_MODE": "1",
        "LANG": "C.UTF-8",
    }
    try:
        child = Popen(
            [executable, "--untrusted", "--outdir", str(directory), str(source)],
            cwd=directory,
            env=env,
            stdin=DEVNULL,
            stdout=log_stream,
            stderr=log_stream,
        )
    finally:
        log_stream.close()
    return {
        "source": str(tex),
        "pid": child.pid,
        "start": time.monotonic(),
        "directory": directory,
        "log": log,
        "rss_sampled_kib": 0,
        "finished": False,
        "child": child,
    }


def _measure_pair(
    pair: tuple[str, str], executable: str, cache: Path, timeout: float, interval: float
) -> dict:
    with tempfile.TemporaryDirectory(prefix="sigma-dual-tectonic-") as tmp:
        parent = Path(tmp).resolve()
        started = []
        max_cgroup_current = 0
        overlap = False
        try:
            for index, name in enumerate(pair):
                source = Path(name).resolve(strict=True)
                started.append(_launch(source, parent, index, executable, cache))
            deadline = time.monotonic() + timeout
            while any(not x["finished"] for x in started):
                active = 0
                for job in started:
                    if job["finished"]:
                        continue
                    pid = job["pid"]
                    waited, status, usage = os.wait4(pid, os.WNOHANG)
                    if waited:
                        job["finished"] = True
                        job["exit_code"] = os.waitstatus_to_exitcode(status)
                        job["peak_rss_kib"] = usage.ru_maxrss
                        job["cpu_seconds"] = round(usage.ru_utime + usage.ru_stime, 3)
                        job["wall_seconds"] = round(time.monotonic() - job["start"], 3)
                        job["child"].returncode = job["exit_code"]
                    else:
                        active += 1
                        job["rss_sampled_kib"] = max(job["rss_sampled_kib"], _rss_kib(pid))
                overlap |= active == 2
                max_cgroup_current = max(max_cgroup_current, _memory_bytes("memory.current") or 0)
                if time.monotonic() > deadline:
                    raise TimeoutError(f"Two-compiler run exceeded {timeout} seconds")
                if active:
                    time.sleep(interval)

            results = []
            for job in started:
                pdf_path = job["directory"] / "report.pdf"
                pdf_size = pdf_path.stat().st_size if pdf_path.is_file() else 0
                valid_pdf = (
                    (
                        pdf_size <= MAX_PDF_BYTES
                        and pdf_size > 4
                        and pdf_path.open("rb").read(5) == b"%PDF-"
                    )
                    if pdf_size
                    else False
                )
                results.append(
                    {
                        "source": job["source"],
                        "exit_code": job["exit_code"],
                        "wall_seconds": job["wall_seconds"],
                        "cpu_seconds": job["cpu_seconds"],
                        "peak_rss_kib": job["peak_rss_kib"],  # Linux wait4; exact child peak
                        "pdf_bytes": pdf_size,
                        "valid_pdf": valid_pdf,
                        "error_tail": (
                            job["log"].read_text(errors="replace")[-500:] if not valid_pdf else ""
                        ),
                    }
                )
            return {
                "simultaneous_compilers_observed": overlap,
                "cgroup_memory_current_sampled_peak_bytes": max_cgroup_current,
                "cgroup_memory_limit_bytes": _memory_bytes("memory.max"),
                "compilers": results,
            }
        finally:
            for job in started:
                if not job["finished"]:
                    try:
                        os.kill(job["pid"], signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    try:
                        pid, status, usage = os.wait4(job["pid"], 0)
                        job["child"].returncode = os.waitstatus_to_exitcode(status)
                    except ChildProcessError:
                        pass


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--timeout", type=float, default=300)
    p.add_argument("--sample-interval", type=float, default=0.025)
    p.add_argument("--output", type=Path, help="Write JSON results for Red's acceptance record")
    args = p.parse_args()
    if args.timeout <= 0 or not 0.005 <= args.sample_interval <= 1:
        p.error("invalid timeout or sample interval")
    executable = shutil.which(os.environ.get("SIGMA_TECTONIC", "tectonic"))
    if not executable:
        p.error("Tectonic binary not available")
    state_dir = Path(os.environ.get("SIGMA_STATE_DIR", str(Path.home() / ".sigma")))
    cache = state_dir / "tectonic-cache"
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    result = {
        "benchmark": "SIGMA dual Tectonic; no AI calls",
        "linux_cgroup": Path("/sys/fs/cgroup/memory.current").is_file(),
        "pairs": [
            _measure_pair(pair, executable, cache, args.timeout, args.sample_interval)
            for pair in FIXTURE_PAIRS
        ],
    }
    payload = json.dumps(result, indent=2)
    print(payload, flush=True)
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    return (
        0
        if all(
            pair["simultaneous_compilers_observed"]
            and all(x["exit_code"] == 0 and x["valid_pdf"] for x in pair["compilers"])
            for pair in result["pairs"]
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
