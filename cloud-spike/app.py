"""Trusted compatibility probe, separate from SIGMA's localhost-only API."""

import asyncio
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "scope": "T22.1 trusted probe; no research API"}


@app.get("/events")
def events() -> StreamingResponse:
    async def stream() -> AsyncIterator[str]:
        for sequence in range(3):
            yield f"id: {sequence}\ndata: checkpoint-{sequence}\n\n"
            await asyncio.sleep(0.05)

    return StreamingResponse(
        stream(), media_type="text/event-stream", headers={"Cache-Control": "no-store"}
    )
