"""Offline acceptance of the local REAL ChatGPT sign-in preview, without provider calls.

Unlike the synthetic OAuth loopback test, this exercises the existing real
authorization routes under local-only gates. No genuine account or network
request is used in CI.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx

import server
import model_gateway
from sigma import api, chatgpt_auth, cloud_auth, personal_browser, personal_inference
from sigma.projects import ProjectError


async def check_research_worker_dispatch() -> None:
    """A verified --prod Personal session must never use direct bearer HTTP."""
    from sigma import personal_inference, research_sessions, research_reference_compiler

    binding = "a" * 64
    credentials = {
        "mode": "chatgpt", "token": "", "transport": "personal_worker",
        "worker_binding": binding, "status": "connected",
    }
    payload = {
        "model": "gpt-6-luna", "store": False, "stream": True,
        "input": [{"role": "user", "content": "Offline test prompt"}],
    }
    response = {
        "status": "completed", "model": "gpt-6-luna",
        "output": [{"content": [{"type": "output_text", "text": "not-json"}]}],
        "usage": {"input_tokens": 12, "output_tokens": 14},
    }
    with (
        patch.object(research_sessions, "_require_current_local_backend"),
        patch.object(research_sessions, "_role_request_payload", return_value=payload),
        patch.object(research_sessions, "_assert_saved_role_input_matches"),
        patch.object(research_sessions, "_session_log_context", return_value=None),
        patch.object(research_sessions, "_sponsor_inference_diagnostic"),
        patch.object(research_sessions, "_call_timeout_seconds", return_value=60.0),
        patch.object(research_sessions, "auth_context", new_callable=AsyncMock, return_value=credentials),
        patch.object(personal_inference, "respond", new_callable=AsyncMock, return_value=response) as worker,
        patch.object(research_sessions.httpx, "AsyncClient",
                     side_effect=AssertionError("Research may not bypass Personal worker")),
    ):
        try:
            await research_sessions._call_provider(
                {"mode": "chatgpt", "model": "gpt-6-luna", "project_path": "/not-used"},
                "investigator", {}, timeout_seconds=30,
            )
        except ProjectError as exc:
            assert "malformed output" in str(exc)
        else:
            raise AssertionError("Malformed offline model response was accepted")
        worker.assert_awaited_once()
        assert worker.await_args.args == (payload,)
        assert worker.await_args.kwargs["expected_binding"] == binding
        assert len(worker.await_args.kwargs["request_id"]) == 32

    frozen = {"sha256": "frozen-digest", "sources": [{"id": "source-1"}]}
    compiled = {
        "guidance": "Apply the source methodology.",
        "selected_source_ids": ["source-1"],
        "omitted_source_ids": [],
        "guidance_sha256": "guidance-digest",
        "source_sha256": "frozen-digest",
    }
    original = {
        "id": "test-session", "status": "queued", "mode": "chatgpt",
        "model": "gpt-6-luna", "research_method_sources": frozen,
        "reference_compilation": {
            "version": research_reference_compiler.VERSION, "status": "pending",
            "source_sha256": "frozen-digest", "attempts": [],
            "required_for_acceptance": True,
        },
    }
    response["output"][0]["content"][0]["text"] = json.dumps({
        "guidance": "Apply the source methodology.",
        "selected_source_ids": ["source-1"], "omitted_source_ids": [],
        "rationale": "Evidence is relevant.",
    })

    @asynccontextmanager
    async def slot():
        yield

    with (
        patch.object(research_sessions, "_session_state_lock", return_value=asyncio.Lock()),
        patch.object(research_sessions, "_read", return_value=original),
        patch.object(research_sessions, "_save"),
        patch.object(research_sessions, "_event"),
        patch.object(research_sessions, "_pause_for_stop_advisory", return_value=False),
        patch.object(research_sessions, "methodology_digest", return_value="frozen-digest"),
        patch.object(research_sessions, "_call_timeout_seconds", return_value=60.0),
        patch.object(research_sessions, "_portfolio_global_gate", side_effect=lambda _: slot()),
        patch.object(research_sessions, "auth_context", new_callable=AsyncMock, return_value=credentials),
        patch.object(research_sessions.cloud_research, "billing_enabled", return_value=False),
        patch.object(research_reference_compiler, "build_request", return_value=payload),
        patch.object(
            research_reference_compiler, "compilation_eligible_sources",
            return_value=[{"id": "source-1"}],
        ),
        patch.object(research_reference_compiler, "validate_result", return_value=compiled),
        patch.object(personal_inference, "respond", new_callable=AsyncMock, return_value=response) as worker,
        patch.object(research_sessions.httpx, "AsyncClient",
                     side_effect=AssertionError("Compiler may not bypass Personal worker")),
    ):
        assert await research_sessions._ensure_reference_compilation(
            "test-session", "/not-used"
        )
        worker.assert_awaited_once()
        assert worker.await_args.args == (payload,)
        assert worker.await_args.kwargs["expected_binding"] == binding
        assert len(worker.await_args.kwargs["request_id"]) == 32
        assert original["reference_compilation"]["status"] == "completed"



async def check_shared_private_model_dispatch() -> None:
    """Every model path reaches the same worker, never a coordinator HTTP request."""
    from pydantic import BaseModel

    from sigma import chat, model_dispatch, papers, personal_inference, proposals

    binding = {
        "mode": "chatgpt",
        "status": "connected",
        "token": "",
        "identity": "private-personal-fixture",
        "transport": "personal_worker",
        "worker_binding": "b" * 64,
    }
    config = {"model": "gpt-6-luna", "reasoning_effort": "medium", "available": True}
    payload = {
        "model": "gpt-6-luna", "store": False, "stream": True,
        "input": [{"role": "user", "content": "offline test"}],
    }
    response = {
        "status": "completed",
        "model": "gpt-6-luna",
        "output": [{"type": "message", "content": [
            {"type": "output_text", "text": '{"value":"ok"}'}
        ]}],
        "usage": {"input_tokens": 20, "output_tokens": 30},
    }

    class SampleOutput(BaseModel):
        value: str

    with patch.object(
        personal_inference, "respond", new_callable=AsyncMock, return_value=response
    ) as rpc:
        actual = await model_dispatch.private_response_if_selected(
            binding, payload, timeout_seconds=3600
        )
        assert actual is response
        assert rpc.await_args.kwargs["timeout_seconds"] == 3600
        assert rpc.await_args.kwargs["expected_binding"] == "b" * 64
        assert len(rpc.await_args.kwargs["request_id"]) == 32
        rpc.reset_mock()
        sponsor = {**binding, "transport": "sponsored", "token": "sponsor-secret"}
        assert await model_dispatch.private_response_if_selected(
            sponsor, payload, timeout_seconds=60
        ) is None
        rpc.assert_not_awaited()
        rpc.return_value = None
        try:
            await model_dispatch.private_response_if_selected(
                binding, payload, timeout_seconds=60
            )
        except ProjectError as exc:
            assert "returned no valid response" in str(exc)
        else:
            raise AssertionError("An invalid private RPC silently fell back to sponsored")
        rpc.return_value = response
        rpc.reset_mock()

    with (
        patch.object(
            personal_inference, "respond", new_callable=AsyncMock, return_value=response
        ) as rpc,
        patch.object(papers.httpx, "AsyncClient",
                     side_effect=AssertionError("Paper bypassed private worker")),
        patch.object(papers.cloud_research, "start_provider_attempt",
                     side_effect=AssertionError("Personal entered sponsored ledger")),
    ):
        for schema in ("sigma_research_qa", "sigma_long_paper_section"):
            output, model = await papers._provider_structured(
                {"question": "offline validation"},
                binding, config, instructions="Return the JSON output.",
                schema_name=schema, response_model=SampleOutput,
            )
            assert output.value == "ok"
            assert model == "gpt-6-luna"
            assert rpc.await_args.kwargs["timeout_seconds"] == 3600
        assert rpc.await_count == 2
        try:
            await papers._provider({}, binding, config, include_diagrams=False)
        except papers.PaperTransientFailure:
            pass  # Mock output deliberately isn't a full PaperDraft schema.
        else:
            raise AssertionError("A malformed one-shot paper was accepted")
        assert rpc.await_count == 3

    response["output"][0]["content"][0]["text"] = "Brainstorm reply"
    with (
        patch.object(chat, "auth_context", new_callable=AsyncMock, return_value=binding),
        patch.object(chat, "models", new_callable=AsyncMock, return_value={
            "connection": {"status": "connected"},
            "models": [{"id": "gpt-6-luna", "availability": "available"}],
        }),
        patch.object(chat.cloud_research, "billing_enabled", return_value=False),
        patch.object(
            personal_inference, "respond", new_callable=AsyncMock, return_value=response
        ) as rpc,
        patch.object(chat.httpx, "AsyncClient",
                     side_effect=AssertionError("Brainstorm bypassed private worker")),
    ):
        answer = await chat.respond(
            speaker="ai_1", messages=[{"speaker": "human", "text": "Hello"}],
            conversation_id="test", expected_binding=binding["identity"],
            model="gpt-6-luna", reasoning_effort="low",
        )
        assert answer == "Brainstorm reply"
        rpc.assert_awaited_once()
        assert rpc.await_args.kwargs["timeout_seconds"] == chat.TIMEOUT_SECONDS

    response["status"] = "failed"
    with (
        patch.object(proposals, "auth_context", new_callable=AsyncMock, return_value=binding),
        patch.object(proposals, "configuration",
                     new_callable=AsyncMock, return_value=config),
        patch.object(proposals, "inspect_project", return_value=SimpleNamespace(
            project=SimpleNamespace(id="test-project"),
        )),
        patch.object(proposals, "suggestion_context_for",
                     return_value=("test-project", "some project context")),
        patch.object(
            personal_inference, "respond", new_callable=AsyncMock, return_value=response
        ) as rpc,
        patch.object(proposals.httpx, "AsyncClient",
                     side_effect=AssertionError("Proposal bypassed private worker")),
    ):
        try:
            await proposals.generate_proposal(
                "/not-used", seed="ignored", suggestion_only=True,
            )
        except ProjectError:
            pass  # The mock explicitly returns an incomplete model response.
        else:
            raise AssertionError("A failed proposal incorrectly completed")
        rpc.assert_awaited_once()

async def main() -> None:
    key = "a" * 64
    with patch.dict(
        os.environ,
        {
            "SIGMA_AUTH_POC_LOCAL_DOCKER": "1",
            "SIGMA_AUTH_POC_REAL_SIGNIN": "1",
            "SIGMA_AUTH_POC_RPC_KEY": key,
        },
    ):
        assert server.real_signin_enabled()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server.app),
            base_url="http://127.0.0.1:8001",
            follow_redirects=False,
        ) as client:
            # Opening the isolated Chromium app goes straight to OpenAI. No
            # interim Connect button, JS paint signal, or popup is required.
            server._ATTEMPT_ID = None
            attempt_id = "test-authorization-id"
            target = "https://auth.openai.com/authorize?state=example"
            with (
                patch.object(
                    server.chatgpt_auth,
                    "session",
                    new_callable=AsyncMock,
                    return_value={"status": "disconnected", "mode": "chatgpt"},
                ),
                patch.object(
                    server.chatgpt_auth,
                    "begin",
                    new_callable=AsyncMock,
                    side_effect=[{"id": attempt_id}, {"id": "fresh-attempt-id"}],
                ) as begin,
                patch.object(server.chatgpt_auth, "cancel") as cancel,
                patch.object(
                    server.chatgpt_auth,
                    "authorization_url",
                    return_value=target,
                ),
                patch.object(
                    server.chatgpt_auth,
                    "attempt_status",
                    return_value={"status": "connecting"},
                ),
            ):
                chooser = await client.get("/")
                assert chooser.status_code in (302, 303, 307, 308)
                assert chooser.headers["location"] == target
                assert "no-store" in chooser.headers["cache-control"]
                # A returned browser may have already consumed the prior
                # one-shot authorization handoff. Reload/reconnect cancels the
                # abandoned attempt and issues a new, single-use URL.
                repeated = await client.get("/")
                assert repeated.headers["location"] == target
                assert begin.await_count == 2
                cancel.assert_called_once_with(attempt_id)
                assert server._ATTEMPT_ID == "fresh-attempt-id"

            server._ATTEMPT_ID = None
            with (
                patch.object(
                    server.chatgpt_auth, "session",
                    new_callable=AsyncMock,
                    return_value={
                        "status": "connected",
                        "mode": "chatgpt",
                        "account": {"plan_authorized": True},
                    },
                ),
                patch.object(server.chatgpt_auth, "begin", new_callable=AsyncMock) as begin,
            ):
                existing = await client.get("/")
                assert existing.status_code == 200
                assert "Continue with ChatGPT" not in existing.text
                begin.assert_not_awaited()

            with patch.object(
                server.chatgpt_auth, "session",
                new_callable=AsyncMock,
                return_value={"status": "unavailable", "mode": "chatgpt"},
            ):
                unavailable = await client.get("/")
                assert unavailable.status_code == 503

            missing_origin = await client.post("/begin")
            assert missing_origin.status_code == 403
            with (
                patch.object(
                    server.chatgpt_auth, "begin",
                    new_callable=AsyncMock,
                    return_value={"id": attempt_id},
                ) as begin,
                patch.object(
                    server.chatgpt_auth, "attempt_status",
                    return_value={"status": "connecting"},
                ),
            ):
                authorized = await client.post(
                    "/begin", headers={"Origin": "http://127.0.0.1:8001"}
                )
                assert authorized.status_code == 200
                assert authorized.json()["id"] == attempt_id
                begin.assert_awaited_once()

            with patch.object(
                server.chatgpt_auth, "authorization_url",
                return_value=target,
            ):
                chooser = await client.get("/open/" + attempt_id)
                assert chooser.status_code in (302, 303, 307, 308)
                assert chooser.headers["location"].startswith("https://auth.openai.com/")
            with patch.object(server, "_saved_preview_is_authorized", return_value=True):
                server._ATTEMPT_ID = None
                preview = await client.get("/preview-state")
                assert preview.status_code == 200
                assert preview.json() == {"phase": "connected"}

        assert model_gateway._valid_rpc_key(
            type("RequestStub", (), {"headers": {"x-sigma-worker-key": key}})()
        )
        assert not model_gateway._valid_rpc_key(
            type("RequestStub", (), {"headers": {}})()
        )
        assert not model_gateway._valid_rpc_key(
            type("RequestStub", (), {"headers": {"x-sigma-worker-key": "0" * 64}})()
        )

    # A saved local user selection must reconnect after the normal launcher
    # stops and restarts its private Docker browser/worker containers.
    principal = cloud_auth.Principal("test-user", "test@example.com", "admin")
    with (
        patch.object(personal_browser, "sign_in_preview_enabled", return_value=True),
        patch.object(
            personal_browser,
            "model_socket",
            new_callable=AsyncMock,
            side_effect=[
                personal_browser.PersonalBrowserUnavailable("worker stopped"),
                "/tmp/private-restored-model.sock",
            ],
        ) as model_socket,
        patch.object(
            personal_browser,
            "session",
            new_callable=AsyncMock,
            return_value={"browser_status": "ready"},
        ) as restore,
    ):
        restored = await personal_inference._socket(principal)
        assert restored == "/tmp/private-restored-model.sock"
        assert model_socket.await_count == 2
        restore.assert_awaited_once_with(principal, action="start")

    with (
        patch.object(personal_browser, "sign_in_preview_enabled", return_value=False),
        patch.object(
            personal_browser,
            "model_socket",
            new_callable=AsyncMock,
            side_effect=personal_browser.PersonalBrowserUnavailable("worker stopped"),
        ),
        patch.object(
            personal_browser, "session", new_callable=AsyncMock
        ) as restore,
    ):
        try:
            await personal_inference._socket(principal)
        except personal_inference.PersonalInferenceUnavailable:
            pass
        else:
            raise AssertionError("Unavailable hosted Personal worker did not fail closed")
        restore.assert_not_awaited()

    # Confirm disconnect must clear locally even when OpenAI discovery is down.
    # Revocation is optional; a provider outage cannot leave bearer credentials
    # saved or a credential lock held while the UI waits for a network timeout.
    credentials = {
        "active": "saved-account",
        "mode": "chatgpt",
        "accounts": {
            "saved-account": {
                "access_token": "fake-access-token",
                "refresh_token": "fake-refresh-token",
                "id_token": "fake-id-token",
                "client_id": "test-client",
            }
        },
    }
    lock_held = False

    @asynccontextmanager
    async def fake_transaction():
        nonlocal lock_held
        lock_held = True
        try:
            yield credentials
        finally:
            lock_held = False

    async def provider_offline():
        assert not lock_held, "Revocation must not run under the credential lock"
        assert "access_token" not in credentials["accounts"]["saved-account"]
        assert "refresh_token" not in credentials["accounts"]["saved-account"]
        raise ProjectError("Provider discovery unavailable")

    with (
        patch.object(chatgpt_auth, "transaction", side_effect=fake_transaction),
        patch.object(chatgpt_auth, "_attempt_store_directory", return_value=Path("/tmp/test-personal")),
        patch.object(chatgpt_auth, "_owner_subject", return_value=None),
        patch.dict(chatgpt_auth._attempts, {}, clear=True),
        patch.object(chatgpt_auth, "discovery", side_effect=provider_offline),
    ):
        result = await chatgpt_auth.disconnect()
    assert result["remote_revocation_confirmed"] is False
    assert lock_held is False
    assert all(
        field not in credentials["accounts"]["saved-account"]
        for field in ("access_token", "refresh_token", "id_token")
    )

    # Only after the isolated worker confirms local disconnect may SIGMA erase
    # the user's Personal authorization and return their selection to Sponsored.
    with (
        patch.object(api, "_personal_browser_principal", return_value=principal),
        patch.object(api.cloud_auth, "config", return_value=SimpleNamespace(local=True)),
        patch.object(api.personal_browser, "sign_in_preview_enabled", return_value=True),
        patch.object(api.personal_inference, "disconnect", new_callable=AsyncMock) as worker_disconnect,
        patch.object(api.cloud_auth, "clear_personal_authorization") as clear_mode,
    ):
        ui_request = httpx.Request("POST", "http://localhost/api/ai/personal-browser/disconnect")
        # The route only reads the already validated request principal.
        from starlette.requests import Request as StarletteRequest
        request = StarletteRequest({
            "type": "http", "method": "POST",
            "path": ui_request.url.path, "headers": [], "query_string": b"",
        })
        response = await api.personal_browser_disconnect(request)
        assert response.status_code == 200
        assert response.body == b'{"disconnected":true}'
        worker_disconnect.assert_awaited_once_with(principal)
        clear_mode.assert_called_once_with(principal.subject)

    with (
        patch.object(api, "_personal_browser_principal", return_value=principal),
        patch.object(api.cloud_auth, "config", return_value=SimpleNamespace(local=True)),
        patch.object(api.personal_browser, "sign_in_preview_enabled", return_value=True),
        patch.object(api.personal_inference, "disconnect", new_callable=AsyncMock,
                     side_effect=personal_inference.PersonalInferenceUnavailable("worker offline")),
        patch.object(api.cloud_auth, "clear_personal_authorization") as clear_mode,
    ):
        try:
            await api.personal_browser_disconnect(request)
        except Exception as error:
            assert getattr(error, "status_code", None) == 503
        else:
            raise AssertionError("Failed worker disconnect incorrectly reported success")
        clear_mode.assert_not_called()

    with patch.dict(os.environ, {"SIGMA_AUTH_POC_REAL_SIGNIN": "0"}):
        assert not server.real_signin_enabled()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server.app),
            base_url="http://127.0.0.1:8001",
        ) as client:
            denied = await client.post(
                "/begin", headers={"Origin": "http://127.0.0.1:8001"}
            )
            assert denied.status_code == 403
    await check_research_worker_dispatch()
    await check_shared_private_model_dispatch()
    print("PASS: private model transport across research, paper, Q/A, Brainstorm and proposals")


if __name__ == "__main__":
    asyncio.run(main())
