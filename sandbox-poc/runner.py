"""Container entrypoint that keeps bounded output files available for host capture."""

from __future__ import annotations

import os
import selectors
import signal
import subprocess
import sys
import time

SAGE = os.environ.get("SIGMA_RESEARCH_RUNTIME") == "sagemath"
EXECUTION_TIMEOUT_SECONDS = 60 if SAGE else 15


def main() -> int:
    header = sys.stdin.buffer.readline(16)
    if not header.endswith(b"\n"):
        return 64
    try:
        size = int(header[:-1])
    except ValueError:
        return 64
    if not 1 <= size <= 16_000:
        return 64
    source = sys.stdin.buffer.read(size)
    if len(source) != size:
        return 64
    token = sys.stdin.buffer.readline(33).strip().decode("ascii", errors="ignore")
    if len(token) != 32 or any(char not in "0123456789abcdef" for char in token):
        return 64
    child_environment = {"MPLCONFIGDIR": "/tmp/matplotlib"}
    program = "import sys; exec(compile(sys.stdin.buffer.read(), '<research>', 'exec'))"
    if SAGE:
        os.makedirs("/tmp/sigma-sage", exist_ok=True)
        child_environment.update(
            HOME="/tmp/sigma-sage",
            DOT_SAGE="/tmp/sigma-sage",
            PATH=os.path.dirname(sys.executable)
            + ":/home/sage/sage/src/bin:/home/sage/sage/local/bin:/usr/bin:/bin",
            OMP_NUM_THREADS="1",
            OPENBLAS_NUM_THREADS="1",
            MKL_NUM_THREADS="1",
        )
        program = (
            "import sys; from sage.all import *; from sage.repl.preparse import preparse; "
            "exec(compile(preparse(sys.stdin.buffer.read().decode('utf-8')), '<research.sage>', 'exec'))"
        )
    child = subprocess.Popen(
        [
            sys.executable,
            "-I",
            "-c",
            program,
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
        start_new_session=True,
        env=child_environment,
    )
    assert child.stdin and child.stdout and child.stderr
    child.stdin.write(source)
    child.stdin.close()
    selector = selectors.DefaultSelector()
    selector.register(child.stdout, selectors.EVENT_READ, sys.stdout.buffer)
    selector.register(child.stderr, selectors.EVENT_READ, sys.stderr.buffer)
    deadline = time.monotonic() + EXECUTION_TIMEOUT_SECONDS
    timed_out = False
    while selector.get_map():
        if time.monotonic() >= deadline:
            timed_out = True
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            # A child may exit while a detached descendant retains its pipes.
            # End the runner even then; container teardown kills descendants.
            break
        for key, _ in selector.select(0.1):
            chunk = os.read(key.fd, 8192)
            if chunk:
                try:
                    key.data.write(chunk)
                    key.data.flush()
                except BrokenPipeError:
                    # Continue consuming until the in-container watchdog can
                    # kill the workload even if the host client disconnects.
                    pass
            else:
                selector.unregister(key.fileobj)
    selector.close()
    return_code = child.wait()
    child.stdout.close()
    child.stderr.close()
    if timed_out:
        sys.stderr.buffer.write(
            f"\nExecution exceeded the {EXECUTION_TIMEOUT_SECONDS}-second wall limit.\n".encode()
        )
    try:
        sys.stdout.buffer.write(b"\x1eSIGMA_DONE:" + token.encode("ascii") + b"\x1f\n")
        sys.stdout.buffer.flush()
    except BrokenPipeError:
        pass
    # The host captures /artifacts while this container remains alive, then
    # closes stdin to release the entrypoint and let docker run exit.
    sys.stdin.buffer.read(1)
    return 124 if timed_out else return_code


if __name__ == "__main__":
    raise SystemExit(main())
