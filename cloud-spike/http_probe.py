"""Real local Worker → FastAPI HTTP/SSE and Chrome probe; no provider calls."""

import asyncio
import os
import time

import httpx
from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8787"


async def main() -> None:
    async with httpx.AsyncClient(base_url=BASE, trust_env=False, timeout=60) as client:
        response = await client.get("/health")
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "ok"
        assert (await client.post("/health")).status_code == 404
        assert (await client.get("/api/projects")).status_code == 404
        responses = await asyncio.gather(*(client.get("/health") for _ in range(3)))
        assert all(response.status_code == 200 for response in responses)
        checkpoints = []
        arrivals = []
        async with client.stream("GET", "/events") as stream:
            assert stream.status_code == 200
            assert stream.headers["content-type"].startswith("text/event-stream")
            async for line in stream.aiter_lines():
                if line.startswith("data: "):
                    checkpoints.append(line[6:])
                    arrivals.append(time.monotonic())
        assert checkpoints == ["checkpoint-0", "checkpoint-1", "checkpoint-2"]
        assert arrivals[-1] - arrivals[0] >= 0.075, "SSE was buffered"
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            executable_path=os.environ.get(
                "SIGMA_BROWSER_EXECUTABLE",
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            ),
            headless=True,
        )
        try:
            page = await browser.new_page()
            await page.goto(BASE + "/health")
            result = await page.evaluate(
                """() => new Promise((resolve, reject) => {
                  const source = new EventSource('/events');
                  const values = [];
                  const timer = setTimeout(() => {
                    source.close(); reject(new Error('SSE deadline'));
                  }, 10000);
                  source.onerror = () => {
                    clearTimeout(timer); source.close(); reject(new Error('SSE error'));
                  };
                  source.onmessage = event => {
                    values.push(event.data);
                    if (values.length === 3) {
                      clearTimeout(timer); source.close(); resolve(values);
                    }
                  };
                })"""
            )
            assert result == checkpoints
        finally:
            await browser.close()
    print(
        "PASS local Worker → FastAPI: health, three clients, route denial, incremental SSE, Chrome EventSource"
    )


if __name__ == "__main__":
    asyncio.run(main())
