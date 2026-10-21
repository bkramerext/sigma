"""A15 offline representation, conversion and safe source-edit scenarios."""

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch

import httpx

from sigma.api import app
from sigma.projects import (
    ProjectError,
    create_strategy,
    initialize_project,
    inspect_project,
    remove_strategy,
)
from sigma.text_conversion import convert_text
from sigma.text_views import digest, inspect_text, save_source

SOURCE = Path("examples/nonconsecutive-subset-sums/project.json")
MODEL = "gpt-6.1-sol"
REAL_CLIENT = httpx.AsyncClient


def provider_output(body: str):
    return {
        "status": "completed",
        "model": MODEL,
        "output": [
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": json.dumps({"body": body, "warnings": []})}
                ],
            }
        ],
    }


async def main_async(root: Path):
    source_before = SOURCE.read_bytes()
    path = root / "stock.sigma"
    path.mkdir()
    (path / "project.json").write_bytes(source_before)
    project_before = (path / "project.json").read_bytes()
    plain = inspect_text(path, "project")
    assert (
        plain["source_format"] == "plain"
        and plain["plain"]["body"] == inspect_project(path).project.problem
    )
    assert plain["markdown"] is None and not (path / "text-representations.json").exists()
    markdown = (
        plain["plain"]["body"]
        .replace("a_n/F_{n+2}", r"$\frac{a_n}{F_{n+2}}$")
        .replace("n >= 0", r"$n \ge 0$")
        .replace("a_12", "$a_{12}$")
        .replace("a_n", "$a_n$")
    )
    calls = []

    async def handler(request):
        body = json.loads(request.content)
        context = json.loads(body["input"])
        calls.append(context)
        assert body["model"] == MODEL and body["reasoning"]["effort"] == "high"
        assert context["text"] == inspect_project(path).project.problem
        output = markdown if context["target_format"] == "markdown" else plain["plain"]["body"]
        return httpx.Response(200, json=provider_output(output))

    def client(**kwargs):
        return REAL_CLIENT(transport=httpx.MockTransport(handler), **kwargs)

    binding = {"identity": "fixture-account", "mode": "api_key", "token": "fixture-only"}
    config = {"available": True, "model": MODEL, "reasoning_effort": "high", "message": "ready"}
    with (
        patch("sigma.text_conversion.auth_context", new=AsyncMock(return_value=binding)),
        patch("sigma.text_conversion.configuration", new=AsyncMock(return_value=config)),
        patch("sigma.text_conversion.httpx.AsyncClient", side_effect=client),
    ):
        converted = await convert_text(
            str(path), "project", "markdown", expected_digest=plain["source_digest"]
        )
        assert converted["markdown"]["current"] and converted["markdown"]["kind"] == "ai_derived"
        assert converted["plain"]["body"] == plain["plain"]["body"]
        assert (path / "project.json").read_bytes() == project_before
        assert SOURCE.read_bytes() == source_before
        assert len(calls) == 1
        assert (await convert_text(str(path), "project", "markdown"))["markdown"]["current"]
        assert len(calls) == 1
        assert inspect_text(path, "project")["markdown"]["body"] == markdown
        assert len(calls) == 1

        edited = markdown + "\n\nKeep the stated proof obligations."
        save_source(path, "project", edited, "markdown", plain["source_digest"])
        after = inspect_text(path, "project")
        assert after["source_format"] == "markdown" and after["markdown"]["body"] == edited
        assert after["plain"] and not after["plain"]["current"]
        assert after["plain"]["body"] == plain["plain"]["body"]
        assert inspect_project(path).project.problem == edited
        assert (path / "project.v5.json").read_bytes() == project_before
        assert inspect_text(path, "project")["source_format"] == "markdown"
        try:
            save_source(path, "project", "stale", "plain", plain["source_digest"])
        except ProjectError:
            pass
        else:
            raise AssertionError("Stale source edit succeeded")
        reverse = await convert_text(str(path), "project", "plain", expected_digest=digest(edited))
        assert reverse["plain"]["current"] and "\\frac" not in reverse["plain"]["body"]
        assert len(calls) == 2
        assert (await convert_text(str(path), "project", "plain"))["plain"]["current"]
        assert len(calls) == 2

    # Legacy v1-v6 documents read without writes, and first representation save
    # only adds the portable companion rather than rewriting project history.
    for version in range(1, 7):
        legacy = root / f"legacy{version}.sigma"
        initialize_project(legacy, "Legacy", "Count a_n for n >= 0")
        raw = json.loads((legacy / "project.json").read_bytes())
        raw["schema_version"] = version
        if version < 6:
            raw.pop("ai_model")
            raw.pop("reasoning_effort")
        if version < 5:
            raw.pop("active_order")
        if version < 4:
            raw.pop("research_mode")
        if version < 2:
            raw.pop("strategies")
        (legacy / "project.json").write_text(json.dumps(raw))
        before = (legacy / "project.json").read_bytes()
        snapshot = inspect_text(legacy, "project")
        assert snapshot["plain"]["body"] == "Count a_n for n >= 0"
        assert (legacy / "project.json").read_bytes() == before
        with (
            patch("sigma.text_conversion.auth_context", new=AsyncMock(return_value=binding)),
            patch("sigma.text_conversion.configuration", new=AsyncMock(return_value=config)),
            patch(
                "sigma.text_conversion.httpx.AsyncClient",
                side_effect=lambda **kwargs: REAL_CLIENT(
                    transport=httpx.MockTransport(
                        lambda request: httpx.Response(
                            200, json=provider_output("Count $a_n$ for $n \\ge 0$")
                        )
                    ),
                    **kwargs,
                ),
            ),
        ):
            result = await convert_text(str(legacy), "project", "markdown")
        assert result["markdown"]["current"]
        assert (legacy / "project.json").read_bytes() == before
        assert inspect_text(legacy, "project")["markdown"]["current"]
    print(
        "PASS v1-v6 read-only legacy access, lazy portable cache, stock source immutability, explicit two-way conversion, stale revision and no cached calls"
    )

    # A pending conversion must never attach to a later human edit.
    race = root / "race.sigma"
    initialize_project(race, "Race", "Count a_n for n >= 0")
    started = asyncio.Event()
    release = asyncio.Event()

    async def pending_handler(request):
        started.set()
        await release.wait()
        return httpx.Response(200, json=provider_output("Count $a_n$ for $n \\ge 0$"))

    with (
        patch("sigma.text_conversion.auth_context", new=AsyncMock(return_value=binding)),
        patch("sigma.text_conversion.configuration", new=AsyncMock(return_value=config)),
        patch(
            "sigma.text_conversion.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(pending_handler), **kwargs
            ),
        ),
    ):
        pending = asyncio.create_task(convert_text(str(race), "project", "markdown"))
        await asyncio.wait_for(started.wait(), 2)
        save_source(
            race, "project", "Count b_n for n >= 0", "plain", digest("Count a_n for n >= 0")
        )
        release.set()
        try:
            await pending
        except ProjectError as exc:
            assert "Source changed" in str(exc)
        else:
            raise AssertionError("Stale conversion was persisted")
        assert inspect_text(race, "project")["markdown"] is None

    # A cancelled transport releases the run gate, with no companion publication.
    cancellation = root / "cancel.sigma"
    initialize_project(cancellation, "Cancel", "Count c_n for n >= 0")
    started.clear()
    release.clear()
    with (
        patch("sigma.text_conversion.auth_context", new=AsyncMock(return_value=binding)),
        patch("sigma.text_conversion.configuration", new=AsyncMock(return_value=config)),
        patch(
            "sigma.text_conversion.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(pending_handler), **kwargs
            ),
        ),
    ):
        pending = asyncio.create_task(convert_text(str(cancellation), "project", "markdown"))
        await asyncio.wait_for(started.wait(), 2)
        pending.cancel()
        try:
            await pending
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError("Cancellation did not interrupt the conversion")
        assert not (cancellation / "text-representations.json").exists()

    # Failures and changed connection state leave the source untouched.
    failure_path = root / "failure.sigma"
    initialize_project(failure_path, "Failure", "Count d_n for n >= 0")
    before = (failure_path / "project.json").read_bytes()
    with (
        patch("sigma.text_conversion.auth_context", new=AsyncMock(return_value=binding)),
        patch(
            "sigma.text_conversion.configuration",
            new=AsyncMock(
                return_value={**config, "available": False, "message": "Selected model unavailable"}
            ),
        ),
    ):
        try:
            await convert_text(str(failure_path), "project", "markdown")
        except ProjectError as exc:
            assert "unavailable" in str(exc)
        else:
            raise AssertionError("Unavailable model was used")
    with (
        patch("sigma.text_conversion.auth_context", new=AsyncMock(return_value=binding)),
        patch("sigma.text_conversion.configuration", new=AsyncMock(return_value=config)),
        patch(
            "sigma.text_conversion.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(200, json=provider_output("x"))
                ),
                **kwargs,
            ),
        ),
    ):
        try:
            await convert_text(str(failure_path), "project", "markdown")
        except ProjectError as exc:
            assert "incomplete" in str(exc)
        else:
            raise AssertionError("Truncated conversion was persisted")
    with (
        patch(
            "sigma.text_conversion.auth_context",
            new=AsyncMock(side_effect=[binding, {**binding, "identity": "other"}]),
        ),
        patch("sigma.text_conversion.configuration", new=AsyncMock(return_value=config)),
        patch(
            "sigma.text_conversion.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(
                        200, json=provider_output("Count $d_n$ for $n \\ge 0$")
                    )
                ),
                **kwargs,
            ),
        ),
    ):
        try:
            await convert_text(str(failure_path), "project", "markdown")
        except ProjectError as exc:
            assert "account/billing" in str(exc)
        else:
            raise AssertionError("Changed account conversion was persisted")
    assert (failure_path / "project.json").read_bytes() == before
    assert not (failure_path / "text-representations.json").exists()
    malformed = provider_output("unused")
    malformed["output"][0]["content"][0]["text"] = "{"
    with (
        patch("sigma.text_conversion.auth_context", new=AsyncMock(return_value=binding)),
        patch("sigma.text_conversion.configuration", new=AsyncMock(return_value=config)),
        patch(
            "sigma.text_conversion.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(lambda request: httpx.Response(200, json=malformed)),
                **kwargs,
            ),
        ),
    ):
        try:
            await convert_text(str(failure_path), "project", "markdown")
        except ProjectError as exc:
            assert "malformed" in str(exc)
        else:
            raise AssertionError("Malformed provider output was persisted")
    assert not (failure_path / "text-representations.json").exists()
    print(
        "PASS in-flight source conflict, cancellation and gate release, unavailable model, truncated output and account change preserve source"
    )

    strategy_path = root / "strategy.sigma"
    initialize_project(strategy_path, "Strategy", "Analyze a_n")
    strategy = create_strategy(
        strategy_path, "Counting route", "Partition a_n by the final digit and check n >= 0"
    ).project.strategies[0]
    original_strategy = strategy.approach
    with (
        patch("sigma.text_conversion.auth_context", new=AsyncMock(return_value=binding)),
        patch("sigma.text_conversion.configuration", new=AsyncMock(return_value=config)),
        patch(
            "sigma.text_conversion.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(
                        200,
                        json=provider_output(
                            "Partition $a_n$ by the final digit and check $n \\ge 0$"
                        ),
                    )
                ),
                **kwargs,
            ),
        ),
    ):
        approach = await convert_text(str(strategy_path), "strategy", "markdown", strategy.id)
    assert approach["markdown"]["current"]
    assert inspect_project(strategy_path).project.strategies[0].approach == original_strategy
    save_source(
        strategy_path,
        "strategy",
        "Partition $a_n$ into two disjoint cases.",
        "markdown",
        digest(original_strategy),
        strategy.id,
    )
    strategy_after = inspect_project(strategy_path).project.strategies[0]
    assert strategy_after.id == strategy.id and strategy_after.title == strategy.title
    assert strategy_after.approach == "Partition $a_n$ into two disjoint cases."
    assert inspect_text(strategy_path, "strategy", strategy.id)["plain"]["current"] is False
    remove_strategy(strategy_path, strategy.id)
    assert inspect_text(strategy_path, "project")["plain"]["current"]

    manual_path = root / "manual.sigma"
    initialize_project(manual_path, "Manual", "Count a_n")
    save_source(manual_path, "project", "Count $a_n$", "markdown", digest("Count a_n"))
    manual = inspect_text(manual_path, "project")
    assert manual["markdown"]["current"] and manual["markdown"]["kind"] == "authored"
    assert manual["plain"] and not manual["plain"]["current"]
    assert manual["plain"]["body"] == "Count a_n"
    cli = await asyncio.to_thread(
        subprocess.run,
        [sys.executable, "-m", "sigma.cli", "text", str(manual_path), "--scope", "project"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(cli.stdout)["source_format"] == "markdown"
    symlinked = root / "symlink.sigma"
    initialize_project(symlinked, "Symlink", "Count e_n")
    (symlinked / "text-representations.json").symlink_to(manual_path / "text-representations.json")
    try:
        inspect_text(symlinked, "project")
    except ProjectError:
        pass
    else:
        raise AssertionError("A linked companion was trusted")

    # ChatGPT-plan mode uses the same strict streamed Responses adapter as proposals.
    plan_path = root / "plan.sigma"
    initialize_project(plan_path, "Plan", "Count a_n for n >= 0")
    plan_binding = {"identity": "plan-fixture", "mode": "chatgpt", "token": "fixture-token"}

    def plan_handler(request):
        payload = json.loads(request.content)
        assert payload["stream"] is True and "max_output_tokens" not in payload
        assert isinstance(payload["input"], list)
        raw = {**provider_output("Count $a_n$ for $n \\ge 0$"), "id": "resp-text-fixture"}
        events = [
            {
                "type": "response.created",
                "sequence_number": 0,
                "response": {"id": "resp-text-fixture", "status": "in_progress"},
            },
            {
                "type": "response.output_text.delta",
                "sequence_number": 1,
                "delta": raw["output"][0]["content"][0]["text"],
            },
            {"type": "response.completed", "sequence_number": 2, "response": raw},
        ]
        content = "".join(
            f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events
        )
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=content)

    with (
        patch("sigma.text_conversion.auth_context", new=AsyncMock(return_value=plan_binding)),
        patch("sigma.text_conversion.configuration", new=AsyncMock(return_value=config)),
        patch(
            "sigma.text_conversion.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(plan_handler), **kwargs
            ),
        ),
    ):
        plan = await convert_text(str(plan_path), "project", "markdown")
    assert plan["markdown"]["current"] and plan["markdown"]["provenance"]["model"] == MODEL
    print(
        "PASS strategy approach shares the service and ChatGPT-plan preserves the selected billing path"
    )

    # The actual ASGI endpoint cancels its provider transport on browser disconnect.
    started.clear()
    release.clear()
    queue: asyncio.Queue[dict] = asyncio.Queue()
    await queue.put(
        {
            "type": "http.request",
            "body": json.dumps(
                {
                    "path": str(cancellation),
                    "scope": "project",
                    "target": "markdown",
                    "expected_digest": digest("Count c_n for n >= 0"),
                }
            ).encode(),
            "more_body": False,
        }
    )
    sent = []

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/projects/text/convert",
        "raw_path": b"/api/projects/text/convert",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"testserver"), (b"content-type", b"application/json")],
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 1234),
    }
    with (
        patch("sigma.text_conversion.auth_context", new=AsyncMock(return_value=binding)),
        patch("sigma.text_conversion.configuration", new=AsyncMock(return_value=config)),
        patch(
            "sigma.text_conversion.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(pending_handler), **kwargs
            ),
        ),
    ):
        serving = asyncio.create_task(app(scope, queue.get, send))
        await asyncio.wait_for(started.wait(), 2)
        await queue.put({"type": "http.disconnect"})
        await asyncio.wait_for(serving, 2)
    assert not (cancellation / "text-representations.json").exists()
    print("PASS ASGI browser disconnect interrupts conversion before companion publication")


def main():
    with TemporaryDirectory() as directory:
        asyncio.run(main_async(Path(directory)))


if __name__ == "__main__":
    main()
