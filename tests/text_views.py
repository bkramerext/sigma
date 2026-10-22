"""A15 offline representation, conversion and safe source-edit scenarios."""

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient

from sigma.api import app
from sigma.projects import (
    ProjectError,
    create_strategy,
    initialize_project,
    inspect_project,
    remove_strategy,
)
from sigma.text_conversion import MAX_CONVERSION_RESPONSE_BYTES, convert_text
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
    path = root / "sample.sigma"
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
        wire_schema = body["text"]["format"]["schema"]
        assert wire_schema == {
            "type": "object",
            "properties": {
                "body": {"type": "string"},
                "warnings": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["body", "warnings"],
            "additionalProperties": False,
        }
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

    # Large strategy descriptions can produce a response envelope above the
    # smaller proposal limit even though the converted body remains bounded.
    large_api_path = root / "large-api-conversion.sigma"
    initialize_project(large_api_path, "Large API conversion", "Review the generated strategy.")
    long_source = " ".join(["Analyze a_n for n >= 0; preserve every assumption."] * 150)
    long_markdown = long_source.replace("a_n", "$a_n$").replace("n >= 0", "$n \\ge 0$")
    long_strategy = create_strategy(
        large_api_path, "Generated long approach", long_source
    ).project.strategies[0]

    def large_json_handler(request):
        raw = provider_output(long_markdown)
        raw["diagnostic_metadata"] = "x" * 140_000
        return httpx.Response(200, json=raw)

    with (
        patch("sigma.text_conversion.auth_context", new=AsyncMock(return_value=binding)),
        patch("sigma.text_conversion.configuration", new=AsyncMock(return_value=config)),
        patch(
            "sigma.text_conversion.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(large_json_handler), **kwargs
            ),
        ),
    ):
        large_api_result = await convert_text(
            str(large_api_path), "strategy", "markdown", long_strategy.id
        )
    assert large_api_result["markdown"]["current"]
    assert large_api_result["markdown"]["body"] == long_markdown
    assert inspect_project(large_api_path).project.strategies[0].approach == long_source
    oversized_path = root / "oversized-conversion.sigma"
    initialize_project(oversized_path, "Oversized conversion", "Review the response bound.")

    def oversized_json_handler(request):
        raw = provider_output("Review the response bound.")
        raw["diagnostic_metadata"] = "x" * (MAX_CONVERSION_RESPONSE_BYTES + 100)
        return httpx.Response(200, json=raw)

    with (
        patch("sigma.text_conversion.auth_context", new=AsyncMock(return_value=binding)),
        patch("sigma.text_conversion.configuration", new=AsyncMock(return_value=config)),
        patch(
            "sigma.text_conversion.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(oversized_json_handler), **kwargs
            ),
        ),
    ):
        try:
            await convert_text(str(oversized_path), "project", "markdown")
        except ProjectError as exc:
            assert "response exceeded the limit" in str(exc)
        else:
            raise AssertionError("An over-limit provider response was accepted")
    assert not (oversized_path / "text-representations.json").exists()
    print("PASS large strategy conversions above 128 KB and the explicit 1 MB response cap")

    # Legacy v1-v6 documents read without writes, and first representation save
    # only adds the portable companion rather than rewriting project history.
    for version in range(1, 7):
        legacy = root / f"legacy{version}.sigma"
        initialize_project(legacy, "Legacy", "Count a_n for n >= 0")
        raw = json.loads((legacy / "project.json").read_bytes())
        raw["schema_version"] = version
        if version < 6:
            raw.pop("ai_model", None)
            raw.pop("reasoning_effort", None)
        if version < 5:
            raw.pop("active_order", None)
        if version < 4:
            raw.pop("research_mode", None)
            raw.pop("investigation_type", None)
        if version < 2:
            raw.pop("strategies", None)
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
        "PASS v1-v6 read-only legacy access, lazy portable cache, sample source immutability, explicit two-way conversion, stale revision and no cached calls"
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

    timeout_path = root / "timeout.sigma"
    initialize_project(timeout_path, "Timeout", "Count t_n for n >= 0")

    async def timeout_handler(request):
        await asyncio.sleep(1)
        return httpx.Response(200, json=provider_output("Count $t_n$ for $n \\ge 0$"))

    with (
        patch("sigma.text_conversion.auth_context", new=AsyncMock(return_value=binding)),
        patch("sigma.text_conversion.configuration", new=AsyncMock(return_value=config)),
        patch("sigma.text_conversion.CALL_SECONDS", 0.01),
        patch(
            "sigma.text_conversion.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(timeout_handler), **kwargs
            ),
        ),
    ):
        try:
            await convert_text(str(timeout_path), "project", "markdown")
        except ProjectError as exc:
            assert "timed out" in str(exc)
        else:
            raise AssertionError("Timed-out conversion was accepted")
    assert (timeout_path / "project.json").is_file()
    assert not (timeout_path / "text-representations.json").exists()
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

    # Connected model discovery does not prove a generation request can succeed.
    # Unknown ChatGPT inference failures must expose only safe status/code metadata.
    rejected_path = root / "rejected-plan.sigma"
    initialize_project(rejected_path, "Rejected plan", "Count a_n for n >= 0")

    def rejected_handler(request):
        payload = json.loads(request.content)
        assert payload["stream"] is True
        return httpx.Response(
            400,
            json={
                "error": {
                    "code": "unsupported_text_format",
                    "type": "invalid_request_error",
                    "param": "text.format.schema",
                    "message": "private research text must not appear in user errors",
                }
            },
        )

    with (
        patch("sigma.text_conversion.auth_context", new=AsyncMock(return_value=plan_binding)),
        patch("sigma.text_conversion.configuration", new=AsyncMock(return_value=config)),
        patch(
            "sigma.text_conversion.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(rejected_handler), **kwargs
            ),
        ),
    ):
        try:
            await convert_text(str(rejected_path), "project", "markdown")
        except ProjectError as exc:
            assert "HTTP 400" in str(exc)
            assert "unsupported_text_format" in str(exc)
            assert "type: invalid_request_error" in str(exc)
            assert "param: text.format.schema" in str(exc)
            assert "private research text" not in str(exc)
        else:
            raise AssertionError("Rejected ChatGPT request was accepted")
    assert not (rejected_path / "text-representations.json").exists()
    print("PASS ChatGPT HTTP rejection preserves source and exposes safe diagnostic code")

    # Admission may return top-level detail instead of error.code.
    from sigma.plan_stream import safe_error_detail

    assert safe_error_detail({"detail": "Unsupported request input format"}) == (
        "Unsupported request input format"
    )
    assert safe_error_detail({"detail": "Bearer secret-that-must-stay-private"}) is None
    assert safe_error_detail({"message": "private research: a_n = F_n"}) is None
    assert safe_error_detail({"error": {"message": "Invalid schema format"}}) == (
        "Invalid schema format"
    )

    def plan_handler(request):
        payload = json.loads(request.content)
        assert payload["stream"] is True and "max_output_tokens" not in payload
        assert "maxLength" not in json.dumps(payload["text"]["format"]["schema"])
        assert "maxItems" not in json.dumps(payload["text"]["format"]["schema"])
        assert isinstance(payload["input"], list)
        assert request.headers.get("accept") == "text/event-stream"
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

    # A connected plan bridge was observed to omit Content-Type on a response.
    # If its body is SSE, dispatch by framing and still require the normal
    # response identity, sequence and terminal-completion checks.
    untyped_path = root / "untyped-plan-stream.sigma"
    initialize_project(untyped_path, "Untyped plan stream", "Count u_n for n >= 0")

    def untyped_plan_handler(request):
        assert request.headers.get("accept") == "text/event-stream"
        text = json.dumps({"body": "Count $u_n$ for $n \\ge 0$", "warnings": []})
        response_id = "resp-untyped-plan"
        events = [
            {
                "type": "response.created",
                "sequence_number": 0,
                "response": {"id": response_id, "status": "in_progress"},
            },
            {"type": "response.output_text.delta", "sequence_number": 1, "delta": text},
            {
                "type": "response.completed",
                "sequence_number": 2,
                "response": {
                    "id": response_id,
                    "status": "completed",
                    "model": MODEL,
                    "output": [],
                },
            },
        ]
        content = "".join(
            f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events
        )
        return httpx.Response(200, content=content)

    with (
        patch("sigma.text_conversion.auth_context", new=AsyncMock(return_value=plan_binding)),
        patch("sigma.text_conversion.configuration", new=AsyncMock(return_value=config)),
        patch(
            "sigma.text_conversion.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(untyped_plan_handler), **kwargs
            ),
        ),
    ):
        untyped_plan = await convert_text(str(untyped_path), "project", "markdown")
    assert untyped_plan["markdown"]["current"]
    assert untyped_plan["markdown"]["body"] == "Count $u_n$ for $n \\ge 0$"

    # Untyped SSE is buffered to identify framing. Keep that path at the same
    # one-megabyte cap as the strict stream parser, and handle large strategy
    # text without dropping or truncating the delta.
    large_plan_path = root / "large-plan-conversion.sigma"
    initialize_project(large_plan_path, "Large plan conversion", "Review the generated strategy.")
    large_plan_strategy = create_strategy(
        large_plan_path, "Generated long plan approach", long_source
    ).project.strategies[0]

    def large_untyped_plan_handler(request):
        output_text = json.dumps({"body": long_markdown, "warnings": []})
        response_id = "resp-large-untyped-plan"
        terminal = {
            **provider_output(long_markdown),
            "id": response_id,
        }
        events = [
            {
                "type": "response.created",
                "sequence_number": 0,
                "response": {"id": response_id, "status": "in_progress"},
            },
            {
                "type": "response.metadata",
                "sequence_number": 1,
                "metadata": "x" * 140_000,
            },
            {
                "type": "response.output_text.delta",
                "sequence_number": 2,
                "delta": output_text,
            },
            {
                "type": "response.completed",
                "sequence_number": 3,
                "response": terminal,
            },
        ]
        content = "".join(
            f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events
        )
        assert len(content.encode()) > 128_000
        return httpx.Response(200, content=content)

    with (
        patch("sigma.text_conversion.auth_context", new=AsyncMock(return_value=plan_binding)),
        patch("sigma.text_conversion.configuration", new=AsyncMock(return_value=config)),
        patch(
            "sigma.text_conversion.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(large_untyped_plan_handler), **kwargs
            ),
        ),
    ):
        large_plan_result = await convert_text(
            str(large_plan_path), "strategy", "markdown", large_plan_strategy.id
        )
    assert large_plan_result["markdown"]["current"]
    assert large_plan_result["markdown"]["body"] == long_markdown
    assert inspect_project(large_plan_path).project.strategies[0].approach == long_source

    partial_path = root / "partial-plan-stream.sigma"
    initialize_project(partial_path, "Partial plan stream", "Count p_n for n >= 0")

    def partial_plan_handler(request):
        response_id = "resp-partial-plan"
        events = [
            {
                "type": "response.created",
                "sequence_number": 0,
                "response": {"id": response_id, "status": "in_progress"},
            },
            {"type": "response.output_text.delta", "sequence_number": 1, "delta": "partial"},
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
                transport=httpx.MockTransport(partial_plan_handler), **kwargs
            ),
        ),
    ):
        try:
            await convert_text(str(partial_path), "project", "markdown")
        except ProjectError as exc:
            assert "without a valid response.completed" in str(exc)
        else:
            raise AssertionError("Partial plan stream was accepted")
    assert not (partial_path / "text-representations.json").exists()

    missing_output_path = root / "missing-output-text.sigma"
    initialize_project(missing_output_path, "Missing output text", "Count o_n for n >= 0")

    def missing_output_handler(request):
        response_id = "resp-missing-output"
        events = [
            {
                "type": "response.created",
                "sequence_number": 0,
                "response": {"id": response_id, "status": "in_progress"},
            },
            {
                "type": "response.completed",
                "sequence_number": 1,
                "response": {
                    "id": response_id,
                    "status": "completed",
                    "model": MODEL,
                    "output": [],
                },
            },
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
                transport=httpx.MockTransport(missing_output_handler), **kwargs
            ),
        ),
    ):
        try:
            await convert_text(str(missing_output_path), "project", "markdown")
        except ProjectError as exc:
            assert "malformed conversion output" in str(exc)
        else:
            raise AssertionError("Completed plan stream without output_text was accepted")
    assert not (missing_output_path / "text-representations.json").exists()
    print(
        "PASS ChatGPT plan untyped SSE recovery, partial/missing-text rejection, and malformed-body classification"
    )

    # The reported sanitized shape `other-object` came from replacing a
    # non-JSON body with `{}` before classifying it as provider rejection.
    # Malformed bodies now stay parse errors and cannot publish a conversion.
    malformed_plan_path = root / "malformed-plan-envelope.sigma"
    initialize_project(malformed_plan_path, "Malformed plan envelope", "Count m_n for n >= 0")
    malformed_source = (malformed_plan_path / "project.json").read_bytes()

    def malformed_plan_handler(request):
        return httpx.Response(200, content=b"<redacted non-JSON provider body>")

    with (
        patch("sigma.text_conversion.auth_context", new=AsyncMock(return_value=plan_binding)),
        patch("sigma.text_conversion.configuration", new=AsyncMock(return_value=config)),
        patch(
            "sigma.text_conversion.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(malformed_plan_handler), **kwargs
            ),
        ),
    ):
        try:
            await convert_text(str(malformed_plan_path), "project", "markdown")
        except ProjectError as exc:
            assert "malformed conversion output" in str(exc)
            assert "ChatGPT rejected the request" not in str(exc)
        else:
            raise AssertionError("Malformed HTTP 200 body was classified as a completion")
    assert (malformed_plan_path / "project.json").read_bytes() == malformed_source
    assert not (malformed_plan_path / "text-representations.json").exists()

    # The API reports that parser failure once as a local 400 and leaves the
    # source and companion store untouched. Known provider errors remain errors.
    api_failure_path = root / "api-malformed-plan.sigma"
    initialize_project(api_failure_path, "API malformed plan", "Count q_n for n >= 0")
    api_source = (api_failure_path / "project.json").read_bytes()
    with (
        patch("sigma.text_conversion.auth_context", new=AsyncMock(return_value=plan_binding)),
        patch("sigma.text_conversion.configuration", new=AsyncMock(return_value=config)),
        patch(
            "sigma.text_conversion.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(malformed_plan_handler), **kwargs
            ),
        ),
        TestClient(app) as api,
    ):
        api_response = api.post(
            "/api/projects/text/convert",
            json={
                "path": str(api_failure_path),
                "scope": "project",
                "target": "markdown",
                "expected_digest": digest("Count q_n for n >= 0"),
            },
        )
    assert api_response.status_code == 400
    assert "malformed conversion output" in api_response.json()["error"]
    assert (api_failure_path / "project.json").read_bytes() == api_source
    assert not (api_failure_path / "text-representations.json").exists()

    # If the plan bridge answers with JSON rather than SSE, accept a complete
    # result and surface a structured provider error without leaking input.
    json_plan_path = root / "json-plan.sigma"
    initialize_project(json_plan_path, "JSON plan", "Count j_n for n >= 0")

    def json_plan_handler(request):
        assert request.headers.get("accept") == "text/event-stream"
        assert json.loads(request.content)["stream"] is True
        return httpx.Response(200, json=provider_output("Count $j_n$ for $n \\ge 0$"))

    with (
        patch("sigma.text_conversion.auth_context", new=AsyncMock(return_value=plan_binding)),
        patch("sigma.text_conversion.configuration", new=AsyncMock(return_value=config)),
        patch(
            "sigma.text_conversion.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(json_plan_handler), **kwargs
            ),
        ),
    ):
        json_plan = await convert_text(str(json_plan_path), "project", "markdown")
    assert json_plan["markdown"]["current"]
    assert json_plan["markdown"]["body"] == "Count $j_n$ for $n \\ge 0$"

    json_error_path = root / "json-plan-error.sigma"
    initialize_project(json_error_path, "JSON plan error", "Count k_n for n >= 0")

    def json_error_handler(request):
        return httpx.Response(
            200,
            json={
                "error": {
                    "code": "subscription_sharing_unsupported_capability",
                    "message": "private source text must stay hidden",
                }
            },
        )

    with (
        patch("sigma.text_conversion.auth_context", new=AsyncMock(return_value=plan_binding)),
        patch("sigma.text_conversion.configuration", new=AsyncMock(return_value=config)),
        patch(
            "sigma.text_conversion.httpx.AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(json_error_handler), **kwargs
            ),
        ),
    ):
        try:
            await convert_text(str(json_error_path), "project", "markdown")
        except ProjectError as exc:
            assert "does not support" in str(exc)
            assert "private source text" not in str(exc)
        else:
            raise AssertionError("JSON ChatGPT plan error was treated as converted text")
    assert not (json_error_path / "text-representations.json").exists()

    # A streaming adapter can omit the assembled text from response.completed,
    # even when all text deltas arrived and the final status is completed.
    # Exercise the actual conversion service, not just a streaming mock helper.
    delta_path = root / "delta-only.sigma"
    initialize_project(delta_path, "Delta-only", "Count a_n for n >= 0")

    def delta_only_handler(request):
        payload = json.loads(request.content)
        assert payload["stream"] is True
        text = json.dumps({"body": "Count $a_n$ for $n \\ge 0$", "warnings": []})
        response_id = "resp-delta-only"
        events = [
            {
                "type": "response.created",
                "sequence_number": 0,
                "response": {"id": response_id, "status": "in_progress"},
            },
            {
                "type": "response.output_text.delta",
                "sequence_number": 1,
                "delta": text[: len(text) // 2],
            },
            {
                "type": "response.output_text.delta",
                "sequence_number": 2,
                "delta": text[len(text) // 2 :],
            },
            {
                "type": "response.completed",
                "sequence_number": 3,
                "response": {
                    "id": response_id,
                    "status": "completed",
                    "model": MODEL,
                    "output": [],
                },
            },
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
                transport=httpx.MockTransport(delta_only_handler), **kwargs
            ),
        ),
    ):
        delta_conversion = await convert_text(str(delta_path), "project", "markdown")
    assert delta_conversion["markdown"]["current"]
    assert delta_conversion["markdown"]["body"] == "Count $a_n$ for $n \\ge 0$"
    print("PASS ChatGPT-plan terminal text omission is recovered from complete streamed deltas")
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
