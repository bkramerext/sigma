"""Provider-free process death at the response/authoritative-commit boundary."""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

import httpx
from provider_replay import ReplayMismatch, request_digest, synthetic_transport

CRASH_EXIT = 73
CREDENTIAL = {
    "identity": "fixture-account",
    "mode": "api_key",
    "token": "fixture-token",
    "status": "connected",
}


def isolated_environment(root: Path) -> dict[str, str]:
    return {
        "SIGMA_STATE_DIR": str(root / "state"),
        "SIGMA_PROJECTS_ROOT": str(root / "projects"),
        "SIGMA_AUTH_HOME": str(root / "auth"),
        "SIGMA_CLOUD_AUTH_ENABLED": "false",
        "SIGMA_REFERENCE_COMPILATION_ENABLED": "false",
    }


async def crash_child(root: Path) -> None:
    from research_sessions import investigation, provider_response, setup, skeptic, wait_for

    from sigma import research_sessions, session_log

    path = root / "projects" / "crash.sigma"
    assert not path.exists(), "The crash fixture must never reuse a project"
    view, strategy, credential, config = await setup(path)
    limits = dict(research_sessions.DEFAULT_LIMITS)
    limits.update(
        research_rounds=2,
        model_calls=4,
        maximum_input_tokens_per_session=1_000_000,
        maximum_estimated_cost_usd=100.0,
    )
    research_sessions.save_limits(str(path), limits)
    outputs = iter((investigation(1), skeptic(1), investigation(2)))
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request_digest(request))
        return httpx.Response(200, json=provider_response(next(outputs)))

    real_call = research_sessions._call_provider

    async def crash_after_response(record, role, context, timeout_seconds=None, step_id=None):
        result = await real_call(record, role, context, timeout_seconds, step_id)
        if len(requests) == 3:
            # A real response has completed, but the production role caller has
            # not yet committed its result. Preserve the preceding acceptance.
            assert role == "investigator" and context["cycle"] == 2
            durable = research_sessions._read(str(path), record["id"])
            assert len(durable["artifacts"]) == 1
            running = next(step for step in durable["steps"] if step["id"] == step_id)
            assert running["status"] == "running"
            session_log.flush()
            verify_transport()
            (root / "crash-marker.json").write_text(
                json.dumps(
                    {
                        "session_id": record["id"],
                        "step_id": step_id,
                        "request_sha256": requests[-1],
                        "accepted_artifact": durable["artifacts"][0],
                    }
                )
            )
            # Deliberately bypass all coroutine cancellation/finalization paths.
            # The OS releases the real worker lock as the process dies.
            os._exit(CRASH_EXIT)
        return result

    with (
        synthetic_transport(credential, config, handler) as verify_transport,
        patch.object(research_sessions, "_call_provider", side_effect=crash_after_response),
    ):
        started = await research_sessions.start_session(
            str(path), strategy.id, str(uuid4()), view.project.id, CREDENTIAL["identity"]
        )
        await wait_for(path, started["id"])
    raise AssertionError("The production response/commit crash boundary was never reached")


async def verify_recovery(root: Path) -> None:
    from research_sessions import MODEL, investigation, provider_response, skeptic, wait_for

    from sigma import research_sessions, session_log

    marker = json.loads((root / "crash-marker.json").read_text())
    path = root / "projects" / "crash.sigma"
    session_id = marker["session_id"]
    config = {"available": True, "model": MODEL, "reasoning_effort": "high"}

    def forbidden(request: httpx.Request) -> httpx.Response:
        raise ReplayMismatch("Recovery dispatched without explicit operator authorization")

    with synthetic_transport(CREDENTIAL, config, forbidden):
        # This is a fresh process with no live worker for the saved session.
        recovered = research_sessions.get_session(str(path), session_id)
        assert recovered["status"] == "paused"
        assert recovered["calls_used"] == 3
        assert "not be retried automatically" in recovered["message"]
        saved = research_sessions._read(str(path), session_id)
        assert saved["artifacts"] == [marker["accepted_artifact"]]
        step = next(item for item in saved["steps"] if item["id"] == marker["step_id"])
        assert step["status"] == "interrupted" and step["attempt_status"] == "unknown"
        liability = next(
            item
            for item in saved["hard_budget_ledger"]["calls"]
            if item["call_id"] == marker["step_id"]
        )
        assert liability["status"] == "unknown"
        assert research_sessions.get_session(str(path), session_id)["status"] == "paused"
        assert research_sessions._read(str(path), session_id) == saved

    outputs = iter((investigation(2), skeptic(2)))
    requests: list[str] = []

    def replacement(request: httpx.Request) -> httpx.Response:
        digest = request_digest(request)
        assert digest != marker["request_sha256"], "A dispatch-unknown request was replayed"
        requests.append(digest)
        return httpx.Response(200, json=provider_response(next(outputs)))

    with synthetic_transport(CREDENTIAL, config, replacement):
        # Explicit repair authorizes a new, separately accounted attempt, not
        # replay of the previous possibly billed request. One extra attempt is
        # needed because the original call ceiling includes the unknown one.
        await research_sessions.control_session(str(path), session_id, "repair", additional_calls=1)
        finished = await wait_for(path, session_id)
        session_log.flush()
    assert finished["status"] == "ended" and len(requests) == 2
    final = research_sessions._read(str(path), session_id)
    artifacts = final["artifacts"]
    assert len(artifacts) == len({item["id"] for item in artifacts}) == 2
    assert artifacts[0] == marker["accepted_artifact"]
    unknown = next(
        item
        for item in final["hard_budget_ledger"]["calls"]
        if item["call_id"] == marker["step_id"]
    )
    assert unknown["status"] == "unknown"
    assert final["calls_used"] == 5
    print(
        "PASS process death after response: original acceptance retained, "
        "unknown liability retained, explicit new work only"
    )


def main() -> None:
    if sys.argv[1:] == ["--crash-child"]:
        root = Path(os.environ["SIGMA_REPLAY_CRASH_ROOT"])
        assert root.name.startswith("sigma-provider-crash-") and root.is_dir()
        assert all(os.environ.get(k) == v for k, v in isolated_environment(root).items())
        asyncio.run(crash_child(root))
        return
    assert not sys.argv[1:]
    with TemporaryDirectory(prefix="sigma-provider-crash-") as directory:
        root = Path(directory)
        for name in ("state", "projects", "auth"):
            (root / name).mkdir(mode=0o700)
        env = isolated_environment(root)
        child = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--crash-child"],
            env={**os.environ, **env, "SIGMA_REPLAY_CRASH_ROOT": str(root)},
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        assert child.returncode == CRASH_EXIT, (child.stdout, child.stderr)
        with patch.dict(os.environ, env):
            asyncio.run(verify_recovery(root))


if __name__ == "__main__":
    main()
