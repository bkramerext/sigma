"""Synthetic SIGMA chat/strategy tests: no tokens, sponsor spend or HTTP fallback."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sigma import agentic, chat, cloud_auth, cloud_personal, cloud_research
from sigma import cloud_workspaces, openai_connection, personal_browser, personal_inference
from sigma.model_catalog import DEFAULT_MODEL
from sigma.projects import ProjectError

BINDING = "b" * 64
MODEL = DEFAULT_MODEL
ACCOUNT = {
    "status": "verified",
    "binding": BINDING,
    "models": [MODEL],
    "account_label": "selected@example.test",
}
RAW = {
    "status": "completed",
    "model": MODEL,
    "output": [
        {
            "type": "message",
            "content": [{"type": "output_text", "text": "synthetic personal reply"}],
        }
    ],
}


async def main() -> None:
    with (
        patch.object(cloud_auth, "config", return_value=SimpleNamespace(local=False)),
        patch.object(personal_browser, "enabled", return_value=True),
        patch.object(personal_inference, "account", new=AsyncMock(return_value=ACCOUNT)),
        patch.object(cloud_workspaces, "enabled", return_value=True),
    ):
        context = await cloud_personal.auth_context("subject-hash")
        assert context["mode"] == "chatgpt"
        assert context["transport"] == "personal_worker"
        assert context["worker_binding"] == BINDING
        assert context["status"] == "connected"
        assert context["token"] == ""
        assert "access_token" not in dict(context)
        catalog = await openai_connection.models(context=context)
        assert catalog["connection"]["status"] == "connected"
        assert catalog["default_verified"] is True
        assert MODEL in {
            item["id"] for item in catalog["models"] if item["availability"] == "available"
        }

        dispatch = AsyncMock(return_value=RAW)
        with (
            patch.object(chat, "auth_context", new=AsyncMock(return_value=context)),
            patch.object(agentic, "auth_context", new=AsyncMock(return_value=context)),
            patch.object(personal_inference, "respond", new=dispatch),
            patch.object(cloud_research, "billing_enabled", return_value=True),
            patch.object(
                cloud_research,
                "start_provider_attempt",
                side_effect=AssertionError("Personal request entered sponsored spend ledger"),
            ),
            patch.object(cloud_research, "settle_provider_attempt", return_value=None),
            patch.object(chat, "cloud_credential", side_effect=AssertionError("Sponsor credential used")),
            patch.object(
                chat.httpx, "AsyncClient", side_effect=AssertionError("Direct provider HTTP used")
            ),
        ):
            config = await chat.configuration()
            assert config["available"] is True
            text = await chat.respond(
                speaker="ai_1",
                messages=[{"speaker": "human", "text": "Hello"}],
                conversation_id="1" * 32,
                expected_binding=context["identity"],
                model=MODEL,
                reasoning_effort="medium",
            )
            assert text == "synthetic personal reply"
            assert dispatch.await_count == 1
            args = dispatch.await_args
            assert args.kwargs["expected_binding"] == BINDING
            assert args.args[0]["stream"] is True
            assert args.args[0]["store"] is False
            assert "Authorization" not in args.args[0]
            assert "token" not in args.args[0]

            # Changing account binding between UI and dispatch must reject.
            try:
                await chat.respond(
                    speaker="ai_1",
                    messages=[{"speaker": "human", "text": "Hello"}],
                    conversation_id="1" * 32,
                    expected_binding="stale-account",
                    model=MODEL,
                    reasoning_effort="medium",
                )
            except ProjectError:
                pass
            else:
                raise AssertionError("Chat accepted an obsolete account binding")
            assert dispatch.await_count == 1

            # The strategy provider must use the same worker transport and
            # never fall back to sponsored billing or provider HTTP.
            dummy_project = SimpleNamespace(id="synthetic-project")
            view = SimpleNamespace(path="/synthetic/workspace", project=dummy_project)
            with (
                patch.object(agentic, "inspect_project", return_value=view),
                patch.object(agentic, "_bounded_context", return_value="synthetic context"),
                patch.object(agentic, "cloud_credential", side_effect=AssertionError("Sponsor used")),
            ):
                try:
                    await agentic._invoke(
                        "explore",
                        {},
                        {"model": MODEL, "reasoning_effort": "medium"},
                        context,
                        view,
                    )
                except ProjectError:
                    # Our small synthetic text does not satisfy the Candidate
                    # JSON schema. Dispatch itself must still have occurred.
                    pass
                else:
                    raise AssertionError("The synthetic strategy response was not schema-checked")
            assert dispatch.await_count == 2
            assert dispatch.await_args.kwargs["expected_binding"] == BINDING
            assert dispatch.await_args.args[0]["store"] is False
            assert dispatch.await_args.args[0]["stream"] is True
        # The real worker remains disabled; simulation cannot enable it.
    print("PASS SIGMA chat/strategies route Personal via worker; sponsor and direct HTTP untouched")


if __name__ == "__main__":
    asyncio.run(main())
