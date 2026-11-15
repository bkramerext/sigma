"""Per-container VNC relay: Unix socket -> this container's localhost:6080.

Only the SIGMA backend receives the private socket mount. Chromium does not
mount this directory. Each browser/worker pair has its own Docker bridge network
and its OAuth callback still uses 127.0.0.1 inside that pair.
"""
from __future__ import annotations

import asyncio
import os
import stat
from pathlib import Path

SOCKET = Path("/run/sigma-personal/vnc.sock")


async def forward(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    upstream_writer: asyncio.StreamWriter | None = None
    try:
        upstream_reader, upstream_writer = await asyncio.wait_for(
            asyncio.open_connection("127.0.0.1", 6080), timeout=5
        )

        async def copy(source: asyncio.StreamReader, target: asyncio.StreamWriter) -> None:
            while True:
                chunk = await source.read(65536)
                if not chunk:
                    return
                target.write(chunk)
                await target.drain()

        tasks = [
            asyncio.create_task(copy(reader, upstream_writer)),
            asyncio.create_task(copy(upstream_reader, writer)),
        ]
        try:
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            for task in done:
                if not task.cancelled():
                    task.result()
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
    except (OSError, TimeoutError, RuntimeError):
        pass
    finally:
        if upstream_writer is not None:
            upstream_writer.close()
            try:
                await upstream_writer.wait_closed()
            except OSError:
                pass
        writer.close()
        try:
            await writer.wait_closed()
        except OSError:
            pass


async def main() -> None:
    root = SOCKET.parent
    details = root.lstat()
    if (
        not stat.S_ISDIR(details.st_mode)
        or root.is_symlink()
        or details.st_uid != os.geteuid()
        or details.st_mode & 0o077
    ):
        raise RuntimeError("Unsafe browser IPC directory")
    if SOCKET.exists() or SOCKET.is_symlink():
        old = SOCKET.lstat()
        if not stat.S_ISSOCK(old.st_mode) or old.st_uid != os.geteuid():
            raise RuntimeError("Unsafe existing browser IPC socket")
        SOCKET.unlink()
    async with await asyncio.start_unix_server(forward, path=str(SOCKET)) as server:
        SOCKET.chmod(0o600)
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
