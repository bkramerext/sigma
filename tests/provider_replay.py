"""Strict, synthetic-only provider replay through the normal research scheduler."""

import asyncio
import hashlib
import itertools
import os
import shutil
import socket
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import httpx

ENDPOINT = "https://api.openai.com/v1/responses"
REAL_CLIENT = httpx.AsyncClient


class ReplayMismatch(AssertionError):
    """A replay must never substitute a response for a different request."""


def request_digest(request: httpx.Request) -> str:
    if request.method != "POST" or str(request.url) != ENDPOINT:
        raise ReplayMismatch("Unexpected provider method or endpoint")
    return hashlib.sha256(request.content).hexdigest()


@dataclass(frozen=True)
class Exchange:
    # Never retain bearer headers or raw request content in the tape.
    request_sha256: str
    response: bytes


class StrictReplay:
    def __init__(self, exchanges: list[Exchange]):
        self.exchanges = tuple(exchanges)
        self.position = 0
        self.failures: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        try:
            digest = request_digest(request)
            if self.position >= len(self.exchanges):
                raise ReplayMismatch(f"Unexpected request at replay slot {self.position + 1}")
            expected = self.exchanges[self.position]
            if digest != expected.request_sha256:
                raise ReplayMismatch(
                    f"Request mismatch at replay slot {self.position + 1}: "
                    f"expected sha256={expected.request_sha256}, received sha256={digest}"
                )
        except ReplayMismatch as exc:
            self.failures.append(str(exc))
            raise
        self.position += 1
        return httpx.Response(
            200, content=expected.response, headers={"content-type": "application/json"}
        )

    def assert_complete(self) -> None:
        # The production worker can catch a dispatch failure. Do not let a
        # later successful attempt hide a mismatch or unconsumed response.
        if self.failures:
            raise ReplayMismatch(self.failures[0])
        if self.position != len(self.exchanges):
            raise ReplayMismatch(
                f"Replay consumed {self.position} of {len(self.exchanges)} recorded responses"
            )


@contextmanager
def deny_network():
    """Fail closed for Python network connections, including DNS and local RPC."""
    attempts = []

    def blocked(*args, **kwargs):
        attempts.append("Unexpected network attempt during offline replay")
        raise ReplayMismatch(attempts[-1])

    with (
        patch.object(socket, "getaddrinfo", side_effect=blocked),
        patch.object(socket.socket, "connect", blocked),
        patch.object(socket.socket, "connect_ex", blocked),
        patch.object(socket.socket, "sendto", blocked),
    ):
        try:
            yield
        finally:
            if attempts:
                raise ReplayMismatch(attempts[0])


def transport_checks() -> None:
    first = httpx.Request("POST", ENDPOINT, content=b'{"input":"synthetic A"}')
    second = httpx.Request("POST", ENDPOINT, content=b'{"input":"synthetic B"}')
    tape = [
        Exchange(request_digest(first), b'{"fixture":1}'),
        Exchange(request_digest(second), b'{}'),
    ]
    replay = StrictReplay(tape)
    assert replay(first).json() == {"fixture": 1}
    assert replay(second).json() == {}
    replay.assert_complete()
    for request in (
        second,
        httpx.Request("GET", ENDPOINT),
        httpx.Request("POST", "https://example.invalid"),
    ):
        replay = StrictReplay(tape)
        try:
            replay(request)
        except ReplayMismatch:
            pass
        else:
            raise AssertionError("A mismatched request received a recorded response")
        assert replay.position == 0 and replay.failures
        try:
            replay.assert_complete()
        except ReplayMismatch:
            pass
        else:
            raise AssertionError("A caught mismatch was hidden")
    replay = StrictReplay(tape)
    replay(first)
    try:
        replay.assert_complete()
    except ReplayMismatch:
        pass
    else:
        raise AssertionError("An incomplete tape was accepted")
    replay(second)
    try:
        replay(first)
    except ReplayMismatch:
        pass
    else:
        raise AssertionError("An extra request received a recorded response")
    try:
        with deny_network():
            socket.getaddrinfo("example.invalid", 443)
    except ReplayMismatch:
        pass
    else:
        raise AssertionError("Offline network guard did not block DNS")
    print("PASS strict matching, endpoint, order, exhaustion, sticky failure, and DNS guard")


async def production_replay(root: Path) -> None:
    from research_sessions import investigation, provider_response, setup, skeptic, wait_for

    from sigma import personal_inference, research_reference_content, research_sessions, session_log

    baseline = root / "baseline.sigma"
    view, strategy, credential, config = await setup(baseline)
    limits = dict(research_sessions.DEFAULT_LIMITS)
    limits.update(research_rounds=1, model_calls=2)
    research_sessions.save_limits(str(baseline), limits)
    before = (baseline / "project.json").read_bytes()
    recorded_path = root / "recorded.sigma"
    replayed_path = root / "replayed.sigma"
    shutil.copytree(baseline, recorded_path)
    shutil.copytree(baseline, replayed_path)
    tape: list[Exchange] = []
    synthetic_outputs = iter((investigation(1), skeptic(1)))

    def record(request: httpx.Request) -> httpx.Response:
        digest = request_digest(request)
        response = httpx.Response(200, json=provider_response(next(synthetic_outputs)))
        tape.append(Exchange(digest, response.content))
        return response

    # Preserve request identity, including generated step IDs and timestamps,
    # without normalizing or ignoring any material input in the replay matcher.
    fixed_time = research_sessions._now()
    key = str(uuid4())

    async def run(path: Path, handler):
        ids = itertools.count(1)
        with (
            deny_network(),
            patch.object(
                research_sessions, "uuid4", side_effect=lambda: UUID(int=next(ids), version=4)
            ),
            patch.object(research_sessions, "_now", return_value=fixed_time),
            patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
            patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
            patch.object(research_sessions, "execution_capabilities", return_value=[]),
            patch.object(
                research_reference_content, "_read_remote", return_value=(404, "", b"", None)
            ),
            patch.object(
                personal_inference,
                "respond",
                side_effect=ReplayMismatch("Unexpected Personal worker dispatch"),
            ) as personal_dispatch,
            patch.object(
                httpx,
                "AsyncClient",
                side_effect=lambda **kwargs: REAL_CLIENT(
                    transport=httpx.MockTransport(handler), **kwargs
                ),
            ),
        ):
            started = await research_sessions.start_session(
                str(path), strategy.id, key, view.project.id, credential["identity"]
            )
            finished = await wait_for(path, started["id"])
            session_log.flush()
            personal_dispatch.assert_not_called()
            return finished

    original = await run(recorded_path, record)
    replay = StrictReplay(tape)
    repeated = await run(replayed_path, replay)
    replay.assert_complete()
    assert len(tape) == 2
    for result in (original, repeated):
        assert result["status"] == "ended" and result["calls_used"] == 2
        assert len(result["artifacts"]) == 1
        assert [step["role"] for step in result["steps"]] == ["investigator", "skeptic"]
    assert original["artifacts"][0]["id"] == repeated["artifacts"][0]["id"]
    assert (
        original["artifacts"][0]["claim_or_question"]
        == repeated["artifacts"][0]["claim_or_question"]
    )
    assert (baseline / "project.json").read_bytes() == before
    assert not research_sessions.list_sessions(str(baseline))
    print("PASS exact provider replay through production session start, dispatch, and acceptance")


def main() -> None:
    transport_checks()
    if sys.argv[1:] == ["--transport-only"]:
        return
    assert not sys.argv[1:], "Usage: provider_replay.py [--transport-only]"
    with TemporaryDirectory(prefix="sigma-provider-replay-") as directory:
        root = Path(directory)
        env = {
            "SIGMA_STATE_DIR": str(root / "state"),
            "SIGMA_PROJECTS_ROOT": str(root / "projects"),
            "SIGMA_AUTH_HOME": str(root / "auth"),
            "SIGMA_REFERENCE_COMPILATION_ENABLED": "false",
        }
        for name in ("state", "projects", "auth"):
            (root / name).mkdir(mode=0o700)
        with patch.dict(os.environ, env):
            asyncio.run(production_replay(root / "projects"))


if __name__ == "__main__":
    main()
