"""Container health probe that checks the worker's model UDS when mounted."""
from __future__ import annotations

import os
import stat
import urllib.request
from pathlib import Path

import httpx

ROOT = Path("/run/sigma-personal")


def main() -> None:
    with urllib.request.urlopen("http://127.0.0.1:8001/health", timeout=3):
        pass
    if not ROOT.exists() and not ROOT.is_symlink():
        return
    details = ROOT.lstat()
    if (
        not stat.S_ISDIR(details.st_mode)
        or ROOT.is_symlink()
        or details.st_uid != os.geteuid()
        or stat.S_IMODE(details.st_mode) != 0o700
    ):
        raise SystemExit("Private relay directory is unsafe")
    vnc = ROOT / "vnc.sock"
    model = ROOT / "model.sock"
    for path in (vnc, model):
        info = path.lstat()
        if not stat.S_ISSOCK(info.st_mode) or path.is_symlink():
            raise SystemExit("Private relay socket is unavailable")
    # The model relay is entirely inside this worker. Verify it is accepting
    # requests; a leftover socket inode is not evidence that the relay lives.
    with httpx.Client(
        transport=httpx.HTTPTransport(uds=str(model)),
        base_url="http://private-model",
        timeout=3,
    ) as client:
        if client.get("/v1/account").status_code != 200:
            raise SystemExit("Private model relay is unavailable")


if __name__ == "__main__":
    main()
