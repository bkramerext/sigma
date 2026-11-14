"""Standalone Personal ChatGPT companion.

This process alone owns its OpenAI login and private credential directory.
SIGMA's web server receives only job results and a revocable pairing capability.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
import webbrowser
from pathlib import Path
from urllib.parse import urlsplit

import httpx


def _validate_server(value: str) -> str:
    parsed = urlsplit(value)
    local = parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}
    if (
        not (parsed.scheme == "https" or local)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or not parsed.hostname
    ):
        raise ValueError("Use an HTTPS SIGMA URL or an exact localhost development address.")
    return value.rstrip("/")


def _prepare_auth_home() -> None:
    # Never touch the standard SIGMA localhost or hosted sponsor credentials.
    # A published app must run as the logged-in OS user.
    parent = Path.home() / ".config"
    parent.mkdir(mode=0o700, exist_ok=True)
    personal = parent / "sigma-personal-companion"
    personal.mkdir(mode=0o700, exist_ok=True)
    os.chmod(personal, 0o700)
    for key in (
        "SIGMA_CLOUD_AUTH_ENABLED",
        "SIGMA_CLOUD_AUTH_LOCAL",
        "SIGMA_CLOUD_WORKSPACES_ROOT",
        "SIGMA_CLOUD_CHATGPT_AUTH_HOME",
        "SIGMA_MOCK_AUTH",
        "SIGMA_OPENAI_API_BASE_URL",
        "OPENAI_API_KEY",
        "SIGMA_CLOUD_OPENAI_API_KEY",
        "SIGMA_CLOUD_OPENAI_API_KEY_FILE",
    ):
        os.environ.pop(key, None)
    os.environ["SIGMA_AUTH_HOME"] = str(personal.resolve())


async def _connect_openai(choose_account: bool) -> tuple[str, str]:
    from sigma import chatgpt_auth
    from sigma.projects import ProjectError

    if not choose_account:
        existing = await chatgpt_auth.session()
        account = existing.get("account") or {}
        if existing.get("status") == "connected" and account.get("access_token"):
            label = account.get("email") or account.get("name") or "ChatGPT account"
            return str(label), str(account.get("subject", ""))

    # This is the *unchanged* OpenAI account chooser and 127.0.0.1 PKCE callback.
    print("Opening OpenAI's ChatGPT account chooser…", flush=True)
    attempt = await chatgpt_auth.begin()
    address = chatgpt_auth.authorization_url(attempt["id"])
    if not webbrowser.open(address):
        chatgpt_auth.cancel(attempt["id"])
        raise ProjectError("No browser could be opened for ChatGPT sign-in.")
    for _ in range(600):
        await asyncio.sleep(0.5)
        state = chatgpt_auth.attempt_status(attempt["id"])
        if state["status"] == "connected":
            selected = await chatgpt_auth.session()
            account = selected.get("account") or {}
            if selected.get("status") != "connected" or not account.get("subject"):
                raise ProjectError("The ChatGPT account was not authorized.")
            return (
                str(account.get("email") or account.get("name") or "ChatGPT account"),
                str(account["subject"]),
            )
        if state["status"] not in {"connecting"}:
            raise ProjectError("ChatGPT sign-in was not completed. Try again.")
    chatgpt_auth.cancel(attempt["id"])
    raise ProjectError("ChatGPT sign-in expired.")


async def _answer(prompt: str) -> tuple[str, str]:
    """Run a real, bounded model turn using local-only credentials."""
    from sigma import chat
    from sigma.projects import ProjectError

    config = await chat.configuration()
    if not config.get("available"):
        raise ProjectError("The selected ChatGPT account has no available reviewed model.")
    model = str(config["model"])
    result = await chat.respond(
        speaker="ai_1",
        messages=[{"speaker": "human", "text": prompt}],
        conversation_id=str(uuid.uuid4()),
        expected_binding=str(config["binding"]),
        model=model,
        reasoning_effort="low",
    )
    return result, model


async def _run(server: str, code: str, choose_account: bool) -> int:
    from sigma.projects import ProjectError

    label, _provider_subject = await _connect_openai(choose_account)
    async with httpx.AsyncClient(
        base_url=server, timeout=httpx.Timeout(20), trust_env=False, follow_redirects=False
    ) as client:
        response = await client.post(
            "/api/personal-companion/worker/redeem",
            json={"code": code},
        )
        response.raise_for_status()
        token = response.json()["token"]
        headers = {"Authorization": "Bearer " + token}
        print("Personal ChatGPT companion paired. Waiting for SIGMA requests.", flush=True)
        try:
            while True:
                try:
                    beat = await client.post(
                        "/api/personal-companion/worker/heartbeat",
                        json={"ready": True, "label": label},
                        headers=headers,
                    )
                    beat.raise_for_status()
                    work = await client.post(
                        "/api/personal-companion/worker/next",
                        json={},
                        headers=headers,
                    )
                    work.raise_for_status()
                except (httpx.TimeoutException, httpx.NetworkError):
                    print("SIGMA is unreachable; Personal jobs are paused.", flush=True)
                    await asyncio.sleep(5)
                    continue
                job = work.json().get("job")
                if job:
                    try:
                        answer, model = await _answer(str(job["prompt"]))
                        failed = False
                    except (ProjectError, ValueError, httpx.HTTPError, TimeoutError):
                        answer, model, failed = "The provider request did not complete.", "", True
                    result = await client.post(
                        "/api/personal-companion/worker/complete",
                        json={
                            "job_id": job["job_id"],
                            "result": answer,
                            "model": model,
                            "failed": failed,
                        },
                        headers=headers,
                    )
                    result.raise_for_status()
                await asyncio.sleep(2)
        finally:
            # Best-effort disconnect; no provider tokens leave this process.
            try:
                await client.post(
                    "/api/personal-companion/worker/disconnect",
                    headers=headers,
                    json={},
                    timeout=3,
                )
            except httpx.HTTPError:
                pass


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SIGMA Personal companion: install once, choose ChatGPT account, pair with SIGMA"
    )
    parser.add_argument("--server", required=True, help="HTTPS SIGMA site or local test origin")
    parser.add_argument("--code", required=True, help="One-time pairing code displayed in SIGMA")
    parser.add_argument("--choose-account", action="store_true", help="Show OpenAI's chooser again")
    args = parser.parse_args()
    try:
        server = _validate_server(args.server)
        _prepare_auth_home()
        raise SystemExit(asyncio.run(_run(server, args.code, args.choose_account)))
    except KeyboardInterrupt:
        print("Personal companion disconnected.")
    except (ValueError, httpx.HTTPError, OSError) as exc:
        print(f"Companion connection could not start: {type(exc).__name__}", file=sys.stderr)
        raise SystemExit(2) from exc
    except Exception as exc:
        from sigma.projects import ProjectError

        if isinstance(exc, ProjectError):
            print("Personal companion sign-in or connection failed; retry.", file=sys.stderr)
            raise SystemExit(2) from exc
        raise


if __name__ == "__main__":
    main()
