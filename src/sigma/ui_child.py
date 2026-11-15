"""Own one server process group; pipe EOF tears it down even if the UI owner crashes."""

import os
import select
import signal
import subprocess
import sys
import time


def main() -> None:
    if os.getpgrp() != os.getpid() or os.getsid(0) != os.getpid():
        print("SIGMA server guardian must be started by the UI supervisor.", file=sys.stderr)
        sys.exit(2)
    stopping = False

    def stop(signum: int, frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    child = None
    try:
        child = subprocess.Popen(sys.argv[1:], stdin=subprocess.DEVNULL)
        while not stopping:
            if child.poll() is not None:
                break
            readable, _, _ = select.select([sys.stdin.buffer], [], [], 0.1)
            if readable and not os.read(0, 1):
                stopping = True
    finally:
        # This wrapper remains the group leader until final cleanup: no PID reuse.
        os.killpg(os.getpgrp(), signal.SIGTERM)
        if child is not None:
            deadline = time.monotonic() + 4
            while child.poll() is None and time.monotonic() < deadline:
                time.sleep(0.05)
        # Also clean surviving descendants after the direct server exits.
        os.killpg(os.getpgrp(), signal.SIGKILL)


if __name__ == "__main__":
    main()
