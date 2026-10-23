"""Container entrypoint that keeps bounded output files available for host capture."""

from __future__ import annotations

import os
import selectors
import subprocess
import sys


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
    token = os.environ.pop("SIGMA_RUNNER_TOKEN", "")
    if len(token) != 32 or any(char not in "0123456789abcdef" for char in token):
        return 64
    child = subprocess.Popen(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; exec(compile(sys.stdin.buffer.read(), '<research>', 'exec'))",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
        env={"MPLCONFIGDIR": "/tmp/matplotlib"},
    )
    assert child.stdin and child.stdout and child.stderr
    child.stdin.write(source)
    child.stdin.close()
    selector = selectors.DefaultSelector()
    selector.register(child.stdout, selectors.EVENT_READ, sys.stdout.buffer)
    selector.register(child.stderr, selectors.EVENT_READ, sys.stderr.buffer)
    while selector.get_map():
        for key, _ in selector.select(0.1):
            chunk = os.read(key.fd, 8192)
            if chunk:
                key.data.write(chunk)
                key.data.flush()
            else:
                selector.unregister(key.fileobj)
    selector.close()
    return_code = child.wait()
    sys.stdout.buffer.write(b"\x1eSIGMA_DONE:" + token.encode("ascii") + b"\x1f\n")
    sys.stdout.buffer.flush()
    # The host captures /artifacts while this container remains alive, then
    # closes stdin to release the entrypoint and let docker run exit.
    sys.stdin.buffer.read(1)
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
