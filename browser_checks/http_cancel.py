import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx

from sigma.projects import initialize_project


async def main():
    with TemporaryDirectory() as d:
        path = Path(d) / "cancel.sigma"
        initialize_project(path, "Cancel transport", "Test disconnect only")
        before = (path / "project.json").read_bytes()
        async with httpx.AsyncClient(timeout=5) as client:
            pending = asyncio.create_task(
                client.post(
                    "http://127.0.0.1:8001/api/projects/proposals",
                    json={"path": str(path), "seed": "timeout-fixture", "consent": True},
                )
            )
            await asyncio.sleep(0.2)
            assert not pending.done()
            pending.cancel()
            try:
                await pending
            except asyncio.CancelledError:
                pass
            await asyncio.sleep(0.2)
            response = await client.post(
                "http://127.0.0.1:8001/api/projects/proposals",
                json={"path": str(path), "seed": "", "consent": True},
            )
            assert response.status_code == 200, response.text
            assert (path / "project.json").read_bytes() == before
    print(
        "PASS real HTTP disconnect cancels adapter request, releases single-request gate and preserves project bytes"
    )


asyncio.run(main())
