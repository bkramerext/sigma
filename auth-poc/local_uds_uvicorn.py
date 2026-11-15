"""Run the synthetic model gateway on a pre-bound Unix socket.

Docker Desktop's Linux VM can create socket nodes in a shared Mac bind mount,
but its chmod operation fails with EINVAL. Binding here and handing the open
socket FD to Uvicorn avoids Uvicorn's chmod step. The host broker sets mode
0600 after both relays are ready; the parent directory is mode 0700 meanwhile.
"""
from __future__ import annotations

import asyncio
import os
import socket

import uvicorn

SOCKET_PATH = "/run/sigma-personal/model.sock"


async def main() -> None:
    os.umask(0o077)
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(SOCKET_PATH)
    listener.listen(128)
    listener.setblocking(False)
    server = uvicorn.Server(
        uvicorn.Config("model_gateway:app", access_log=False, log_config=None)
    )
    await server.serve(sockets=[listener])


if __name__ == "__main__":
    asyncio.run(main())
