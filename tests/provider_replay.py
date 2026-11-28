"""Strict, synthetic-only provider replay through the normal research scheduler."""

import asyncio
import base64
import hashlib
import inspect
import itertools
import json
import os
import re
import shutil
import socket
import ssl
import sys
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, tzinfo
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


MAX_EXCHANGES = 32
MAX_BODY_BYTES = 256_000
MAX_TAPE_BYTES = 2_000_000
MAX_CHUNKS = 32
TAPE_VERSION = 1
JSON_TYPE = "application/json"
SSE_TYPE = "text/event-stream"


def request_lane(request: httpx.Request) -> str:
    try:
        payload = json.loads(request.content)
        context = payload["input"]
        if isinstance(context, list):
            context = context[0]["content"]
        lane = json.loads(context)["strategy"]["id"]
        if not isinstance(lane, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", lane):
            raise ValueError("invalid strategy identity")
        return lane
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ReplayMismatch("Request has no valid strategy identity") from exc


class FixtureStream(httpx.AsyncByteStream):
    def __init__(self, chunks: tuple[bytes, ...]):
        self.chunks = chunks

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk


@dataclass(frozen=True)
class Exchange:
    # Only synthetic fixture responses and exact request digests, never raw
    # requests, bearer headers, private model recordings or unknown attempts.
    request_sha256: str
    response: bytes
    status: int = 200
    content_type: str = JSON_TYPE
    lane: str = "default"
    chunk_sizes: tuple[int, ...] = ()

    def __post_init__(self):
        if (
            not isinstance(self.request_sha256, str)
            or not re.fullmatch(r"[0-9a-f]{64}", self.request_sha256)
            or not isinstance(self.response, bytes)
            or len(self.response) > MAX_BODY_BYTES
            or type(self.status) is not int
            or not (self.status == 200 or 400 <= self.status <= 599)
            or self.content_type not in (JSON_TYPE, SSE_TYPE)
            or not isinstance(self.lane, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", self.lane)
            or not isinstance(self.chunk_sizes, tuple)
            or len(self.chunk_sizes) > MAX_CHUNKS
            or any(type(size) is not int or size <= 0 for size in self.chunk_sizes)
            or (self.chunk_sizes and sum(self.chunk_sizes) != len(self.response))
            or (self.content_type == SSE_TYPE and not self.chunk_sizes)
        ):
            raise ReplayMismatch("Invalid or oversized synthetic tape exchange")

    def make_response(self) -> httpx.Response:
        headers = {"content-type": self.content_type}
        if self.chunk_sizes:
            chunks = []
            offset = 0
            for size in self.chunk_sizes:
                chunks.append(self.response[offset : offset + size])
                offset += size
            return httpx.Response(self.status, stream=FixtureStream(tuple(chunks)), headers=headers)
        return httpx.Response(self.status, content=self.response, headers=headers)


def validate_tape(exchanges: list[Exchange]) -> None:
    if (
        not exchanges
        or len(exchanges) > MAX_EXCHANGES
        or sum(len(item.response) for item in exchanges) > MAX_TAPE_BYTES
    ):
        raise ReplayMismatch("Empty or oversized synthetic tape")
    lanes = {item.lane for item in exchanges}
    if "default" in lanes and len(lanes) != 1:
        raise ReplayMismatch("Default and strategy-specific tape lanes cannot be mixed")


def encode_tape(exchanges: list[Exchange]) -> bytes:
    validate_tape(exchanges)
    return json.dumps(
        {
            "version": TAPE_VERSION,
            "origin": "synthetic_fixture_only",
            "endpoint": ENDPOINT,
            "method": "POST",
            "exchanges": [
                {
                    "request_sha256": item.request_sha256,
                    "response_b64": base64.b64encode(item.response).decode("ascii"),
                    "status": item.status,
                    "content_type": item.content_type,
                    "lane": item.lane,
                    "chunk_sizes": item.chunk_sizes,
                }
                for item in exchanges
            ],
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def decode_tape(raw: bytes) -> list[Exchange]:
    if not isinstance(raw, bytes) or len(raw) > 2 * MAX_TAPE_BYTES:
        raise ReplayMismatch("Oversized synthetic tape encoding")
    try:
        document = json.loads(raw)
        if (
            not isinstance(document, dict)
            or set(document) != {"version", "origin", "endpoint", "method", "exchanges"}
            or type(document["version"]) is not int
            or document["version"] != TAPE_VERSION
            or document["origin"] != "synthetic_fixture_only"
            or document["endpoint"] != ENDPOINT
            or document["method"] != "POST"
            or not isinstance(document["exchanges"], list)
            or not 1 <= len(document["exchanges"]) <= MAX_EXCHANGES
        ):
            raise ReplayMismatch("Unsupported synthetic tape contract")
        result = []
        for item in document["exchanges"]:
            if (
                not isinstance(item, dict)
                or set(item)
                != {
                    "request_sha256",
                    "response_b64",
                    "status",
                    "content_type",
                    "lane",
                    "chunk_sizes",
                }
                or not isinstance(item["response_b64"], str)
                or len(item["response_b64"]) > 2 * MAX_BODY_BYTES
                or not isinstance(item["chunk_sizes"], list)
                or len(item["chunk_sizes"]) > MAX_CHUNKS
            ):
                raise ReplayMismatch("Invalid synthetic tape exchange encoding")
            result.append(
                Exchange(
                    item["request_sha256"],
                    base64.b64decode(item["response_b64"], validate=True),
                    item["status"],
                    item["content_type"],
                    item["lane"],
                    tuple(item["chunk_sizes"]),
                )
            )
        validate_tape(result)
        return result
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ReplayMismatch("Invalid synthetic tape encoding") from exc


class StrictReplay:
    def __init__(self, exchanges: list[Exchange]):
        validate_tape(exchanges)
        self.exchanges = tuple(exchanges)
        self.lanes: dict[str, list[Exchange]] = {}
        for item in exchanges:
            self.lanes.setdefault(item.lane, []).append(item)
        self.offsets = dict.fromkeys(self.lanes, 0)
        self.position = 0
        self.failures: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        try:
            if self.failures:
                raise ReplayMismatch(self.failures[0])
            digest = request_digest(request)
            lane = "default" if "default" in self.lanes else request_lane(request)
            if lane not in self.lanes:
                raise ReplayMismatch("Unexpected strategy lane")
            offset = self.offsets[lane]
            if offset >= len(self.lanes[lane]):
                raise ReplayMismatch(f"Unexpected request at replay slot {offset + 1}")
            expected = self.lanes[lane][offset]
            if digest != expected.request_sha256:
                raise ReplayMismatch(
                    f"Request mismatch at replay slot {offset + 1}: "
                    f"expected sha256={expected.request_sha256}, received sha256={digest}"
                )
        except ReplayMismatch as exc:
            self.failures.append(str(exc))
            raise
        self.offsets[lane] += 1
        self.position += 1
        return expected.make_response()

    def assert_complete(self) -> None:
        if self.failures:
            raise ReplayMismatch(self.failures[0])
        if self.position != len(self.exchanges):
            raise ReplayMismatch(
                f"Replay consumed {self.position} of {len(self.exchanges)} recorded responses"
            )


@contextmanager
def deny_network():
    """Guard Python socket/DNS paths; not a native-code or subprocess sandbox."""
    attempts = []

    def blocked(*args, **kwargs):
        attempts.append("Unexpected network attempt during offline replay")
        raise ReplayMismatch(attempts[-1])

    def verify():
        if attempts:
            raise ReplayMismatch(attempts[0])

    def guard_send(original):
        def send(sock, *args, **kwargs):
            # asyncio uses an already-connected local socketpair for wakeups.
            # New connections (including local RPC) remain forbidden.
            if sock.family == socket.AF_UNIX:
                return original(sock, *args, **kwargs)
            return blocked()

        return send

    with ExitStack() as stack:
        for name in (
            "getaddrinfo",
            "gethostbyname",
            "gethostbyname_ex",
            "gethostbyaddr",
            "getnameinfo",
        ):
            stack.enter_context(patch.object(socket, name, side_effect=blocked))
        for name in ("connect", "connect_ex", "sendto"):
            stack.enter_context(patch.object(socket.socket, name, blocked))
        for cls in (socket.socket, ssl.SSLSocket):
            for name in ("send", "sendall", "sendmsg", "sendfile", "write"):
                if hasattr(cls, name):
                    original = getattr(cls, name)
                    stack.enter_context(patch.object(cls, name, guard_send(original)))
        try:
            yield verify
        finally:
            verify()


def network_guard_checks() -> None:
    # No actual network activity: unconnected Internet socket calls must fail
    # before the OS sees them, and DNS names are never resolved.
    def expect_sticky_failure(action):
        try:
            with deny_network():
                try:
                    action()
                except ReplayMismatch:
                    pass
                else:
                    raise AssertionError("Network guard allowed an unexpected operation")
        except ReplayMismatch:
            pass
        else:
            raise AssertionError("Caught network violation was not sticky")

    expect_sticky_failure(lambda: socket.getaddrinfo("example.invalid", 443))
    expect_sticky_failure(lambda: socket.gethostbyname("example.invalid"))
    expect_sticky_failure(lambda: socket.gethostbyname_ex("example.invalid"))
    expect_sticky_failure(lambda: socket.gethostbyaddr("127.0.0.1"))
    expect_sticky_failure(lambda: socket.getnameinfo(("127.0.0.1", 443), 0))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as internet_socket:
        expect_sticky_failure(lambda: internet_socket.connect(("127.0.0.1", 1)))
        expect_sticky_failure(lambda: internet_socket.connect_ex(("127.0.0.1", 1)))
        expect_sticky_failure(lambda: internet_socket.send(b"fixture"))
        expect_sticky_failure(lambda: internet_socket.sendall(b"fixture"))
        if hasattr(internet_socket, "sendmsg"):
            expect_sticky_failure(lambda: internet_socket.sendmsg([b"fixture"]))
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as datagram:
        expect_sticky_failure(lambda: datagram.sendto(b"fixture", ("127.0.0.1", 1)))
    with ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT).wrap_socket(
        socket.socket(socket.AF_INET, socket.SOCK_STREAM), server_hostname="example.invalid"
    ) as tls_socket:
        expect_sticky_failure(lambda: tls_socket.send(b"fixture"))
        expect_sticky_failure(lambda: tls_socket.sendall(b"fixture"))
        expect_sticky_failure(lambda: tls_socket.write(b"fixture"))
    local, peer = socket.socketpair()
    with local, peer, deny_network():
        local.sendall(b"x")
        assert peer.recv(1) == b"x"
    print("PASS sticky DNS/socket egress guard and local event-loop wakeups")


@contextmanager
def synthetic_transport(credential, config, handler):
    """Use the production HTTP client with an offline-only transport."""
    from sigma import personal_inference, research_reference_content, research_sessions

    failures: list[str] = []

    async def guarded(request):
        try:
            result = handler(request)
            return await result if inspect.isawaitable(result) else result
        except ReplayMismatch as exc:
            failures.append(str(exc))
            raise

    with (
        deny_network() as verify_network,
        patch.object(research_sessions, "auth_context", new=AsyncMock(return_value=credential)),
        patch.object(research_sessions, "configuration", new=AsyncMock(return_value=config)),
        patch.object(
            research_sessions, "_frozen_session_configuration", new=AsyncMock(return_value=config)
        ),
        patch.object(research_sessions, "execution_capabilities", return_value=[]),
        patch.object(research_reference_content, "_read_remote", return_value=(404, "", b"", None)),
        patch.object(
            personal_inference,
            "respond",
            side_effect=ReplayMismatch("Unexpected Personal worker dispatch"),
        ) as private_dispatch,
        patch.object(
            httpx,
            "AsyncClient",
            side_effect=lambda **kwargs: REAL_CLIENT(
                transport=httpx.MockTransport(guarded), **kwargs
            ),
        ),
    ):

        def verify():
            verify_network()
            private_dispatch.assert_not_called()
            if failures:
                raise ReplayMismatch(failures[0])

        try:
            yield verify
        finally:
            verify()


def transport_checks() -> None:
    first = httpx.Request("POST", ENDPOINT, content=b'{"input":"synthetic A"}')
    second = httpx.Request("POST", ENDPOINT, content=b'{"input":"synthetic B"}')
    tape = [
        Exchange(request_digest(first), b'{"fixture":1}'),
        Exchange(request_digest(second), b"{}"),
    ]
    assert decode_tape(encode_tape(tape)) == tape
    for malformed in (b"{}", b"not JSON", b" " * (2 * MAX_TAPE_BYTES + 1)):
        try:
            decode_tape(malformed)
        except ReplayMismatch:
            pass
        else:
            raise AssertionError("Malformed or oversized tape accepted")
    replay = StrictReplay(decode_tape(encode_tape(tape)))
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
    network_guard_checks()
    print("PASS strict matching, endpoint, order, exhaustion, sticky failure, and DNS guard")


def fixed_scheduler_clock(timestamp: str) -> type[datetime]:
    """Freeze only the research scheduler's wall clock, not asyncio or I/O."""
    fixed = datetime.fromisoformat(timestamp)

    class SchedulerClock(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> datetime:
            if tz is None:
                return fixed.astimezone().replace(tzinfo=None)
            return fixed.astimezone(tz)

    return SchedulerClock


@contextmanager
def fixed_attempt_clock(duration: float):
    """Patch only RED's persisted attempt clock, when the contract is present."""
    from sigma import research_sessions

    if not hasattr(research_sessions, "_provider_attempt_clock"):
        yield False
        return
    # Each worker task owns its own counter; overlapping provider calls cannot
    # advance another task's interval. Exact binary fractions avoid rounding drift.
    ticks: dict[asyncio.Task | None, int] = {}

    def now() -> float:
        task = asyncio.current_task()
        tick = ticks.get(task, 0)
        ticks[task] = tick + 1
        return 100.0 + tick * duration

    with patch.object(research_sessions, "_provider_attempt_clock", side_effect=now):
        yield True
    assert ticks and all(count % 2 == 0 for count in ticks.values())


def assert_attempt_timing(result: dict, duration: float, *, enabled: bool) -> None:
    observability = result["outcome"]["metrics"].get("observability", {})
    if not enabled:
        assert "provider_attempt_seconds" not in observability, (
            "Integrated attempt metrics require the shared provider clock seam"
        )
        return
    steps = result["steps"]
    assert steps and all(step["provider_attempt_duration_seconds"] == duration for step in steps)
    assert observability["provider_attempt_seconds"] == duration * len(steps)


async def production_replay(root: Path) -> None:
    from research_sessions import investigation, provider_response, setup, skeptic, wait_for

    from sigma import research_sessions, session_log

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

    async def run(path: Path, handler, *, duration=0.125):
        ids = itertools.count(1)
        with (
            patch.object(
                research_sessions, "uuid4", side_effect=lambda: UUID(int=next(ids), version=4)
            ),
            patch.object(research_sessions, "datetime", fixed_scheduler_clock(fixed_time)),
            synthetic_transport(credential, config, handler),
            fixed_attempt_clock(duration) as timing_enabled,
        ):
            started = await research_sessions.start_session(
                str(path), strategy.id, key, view.project.id, credential["identity"]
            )
            finished = await wait_for(path, started["id"])
            session_log.flush()
            assert_attempt_timing(finished, duration, enabled=timing_enabled)
            return finished

    original = await run(recorded_path, record)
    fixture_path = root / "synthetic-api-tape.json"
    fixture_path.write_bytes(encode_tape(tape))
    replay = StrictReplay(decode_tape(fixture_path.read_bytes()))
    repeated = await run(replayed_path, replay)
    replay.assert_complete()
    assert len(tape) == 2
    for result in (original, repeated):
        assert result["status"] == "ended" and result["calls_used"] == 2
        assert len(result["artifacts"]) == 1
        assert [step["role"] for step in result["steps"]] == ["investigator", "skeptic"]
    assert_accepted_equivalence(original, repeated)
    if hasattr(research_sessions, "_provider_attempt_clock"):
        timing_path = root / "timedrep.sigma"
        shutil.copytree(baseline, timing_path)
        timing_replay = StrictReplay(decode_tape(fixture_path.read_bytes()))
        changed = await run(timing_path, timing_replay, duration=0.5)
        timing_replay.assert_complete()
        assert changed["calls_used"] == original["calls_used"]
        assert changed["status"] == original["status"]
        assert [step["provider_input_audit"]["request_body_sha256"] for step in changed["steps"]] == [
            item.request_sha256 for item in tape
        ]
        differences = outcome_difference_paths(original["outcome"], changed["outcome"])
        assert "outcome.metrics.observability.provider_attempt_seconds" in differences, differences
        try:
            assert_accepted_equivalence(original, changed)
        except AssertionError as exc:
            assert "outcome.metrics.observability.provider_attempt_seconds" in str(exc), str(exc)
        else:
            raise AssertionError("Strict replay accepted changed provider timing")
        print("PASS actual persisted provider timing drift rejected by strict outcome equality")
    else:
        print("UNVERIFIED integrated attempt clock: RED seam not present on standalone head")
    assert [step["provider_input_audit"]["request_body_sha256"] for step in original["steps"]] == [
        item.request_sha256 for item in tape
    ]
    assert (baseline / "project.json").read_bytes() == before
    assert not research_sessions.list_sessions(str(baseline))
    print("PASS exact provider replay through production session start, dispatch, and acceptance")

    def forbidden(request: httpx.Request) -> httpx.Response:
        raise ReplayMismatch("History activation dispatched a provider request")

    with synthetic_transport(credential, config, forbidden):
        verify_history_migration(root, recorded_path, original)


def verify_history_migration(root: Path, source: Path, result: dict) -> None:
    """Migrate real accepted synthetic research, not an empty mock session."""
    from sigma import research_sessions
    from sigma.project_bundle import import_bundle, read_file
    from sigma.projects import inspect_project, migrate_project

    session_id = result["id"]
    session_member = f"research-sessions/{session_id}.json"
    artifact_member = "artifacts/replay-fixture.bin"
    artifact = source / artifact_member
    artifact.parent.mkdir(exist_ok=True)
    artifact.write_bytes(b"synthetic historical artifact\x00\xff")
    originals = {
        member: read_file(source, member)
        for member in ("project.json", session_member, artifact_member)
    }
    migrated = migrate_project(source)
    assert all(read_file(migrated.path, name) == raw for name, raw in originals.items())
    assert all(read_file(source, name) == raw for name, raw in originals.items())
    assert migrated.project == inspect_project(source).project
    # Migration is an archival copy. Import is the supported activation path:
    # it validates and rekeys sessions instead of opening the archive as a
    # second executable project with the same session identity.
    archived = json.loads(read_file(migrated.path, session_member))
    assert archived["id"] == session_id
    assert archived["project_path"] == str(source.resolve())
    assert archived["artifacts"] == result["artifacts"]
    assert [step["role"] for step in archived["steps"]] == ["investigator", "skeptic"]

    legacy = {
        "format": "sigma.project.bundle",
        "version": 1,
        "files": {name: base64.b64encode(raw).decode() for name, raw in originals.items()},
    }
    identities = {session_id}
    for name, payload in (
        ("activated-history.json", json.loads(Path(migrated.path).read_text())),
        ("legacy-history-import.json", legacy),
    ):
        imported = root / name
        import_bundle(payload, imported)
        assert read_file(imported, artifact_member) == originals[artifact_member]
        assert inspect_project(imported).project.id == migrated.project.id
        sessions, unavailable = research_sessions.read_session_snapshot(str(imported))
        assert unavailable == 0 and len(sessions) == 1
        saved = sessions[0]
        new_id = saved["id"]
        assert new_id not in identities
        identities.add(new_id)
        assert saved["source_session_id"] == session_id
        assert saved["project_path"] == str(imported.resolve())
        assert saved["idempotency_key"] != archived["idempotency_key"]
        visible = research_sessions.get_session(str(imported), new_id)
        assert visible["status"] == result["status"] == "ended"
        assert visible["calls_used"] == result["calls_used"] == 2
        assert len(visible["artifacts"]) == 1
        assert [step["role"] for step in visible["steps"]] == ["investigator", "skeptic"]
        actual, expected = visible["artifacts"][0], result["artifacts"][0]
        for field in ("id", "claim_or_question", "reasoning_steps", "skeptic_output"):
            assert actual[field] == expected[field], field
        assert [step["id"] for step in saved["steps"]] == [step["id"] for step in archived["steps"]]
        assert [step["status"] for step in saved["steps"]] == [
            step["status"] for step in archived["steps"]
        ]
    assert (
        research_sessions.get_session(str(source), session_id)["artifacts"] == result["artifacts"]
    )
    assert all(read_file(source, name) == raw for name, raw in originals.items())
    assert all(read_file(migrated.path, name) == raw for name, raw in originals.items())
    print(
        "PASS archival migration and supported activation preserve accepted history and identities"
    )


def outcome_difference_paths(left, right, path="outcome") -> list[str]:
    """Report structural mismatch locations without dumping response contents."""
    if type(left) is not type(right):
        return [f"{path} (type mismatch)"]
    if isinstance(left, dict):
        differences = [f"{path}.{key} (missing key)" for key in sorted(left.keys() ^ right.keys())]
        for key in sorted(left.keys() & right.keys()):
            differences.extend(outcome_difference_paths(left[key], right[key], f"{path}.{key}"))
        return differences
    if isinstance(left, list):
        differences = [f"{path} (length mismatch)"] if len(left) != len(right) else []
        for index, (first, second) in enumerate(zip(left, right, strict=False)):
            differences.extend(outcome_difference_paths(first, second, f"{path}[{index}]"))
        return differences
    return [path] if left != right else []


def assert_accepted_equivalence(left: dict, right: dict) -> None:
    # Compare substantive artifact fields and the entire outcome, including metrics.
    fields = (
        "id",
        "strategy_id",
        "claim_or_question",
        "investigator_output",
        "skeptic_output",
        "reasoning_steps",
        "open_obligations",
        "objective_review",
        "coordinator_decision",
        "next_question",
    )
    assert len(left["artifacts"]) == len(right["artifacts"])
    for first, second in zip(left["artifacts"], right["artifacts"], strict=True):
        for field in fields:
            assert first[field] == second[field], field
    assert left["outcome"] == right["outcome"], outcome_difference_paths(
        left["outcome"], right["outcome"]
    )[:20]
    assert left["termination_reason_code"] == right["termination_reason_code"]
    assert left["calls_used"] == right["calls_used"]
    assert left["status"] == right["status"]
    branch_fields = ("strategy_id", "status", "calls_used", "cycle", "current_question")
    for first, second in zip(left["strategy_runs"], right["strategy_runs"], strict=True):
        for field in branch_fields:
            assert first[field] == second[field], field
    assert [
        (step["role"], step["status"], step["provider_input_audit"]["request_body_sha256"])
        for step in left["steps"]
    ] == [
        (step["role"], step["status"], step["provider_input_audit"]["request_body_sha256"])
        for step in right["steps"]
    ]


async def parallel_stream_replay(root: Path) -> None:
    """Replay overlapping real strategy sessions, with a known rejection/retry."""
    from research_sessions import investigation, provider_response, setup, skeptic, wait_for

    from sigma import research_sessions, session_log
    from sigma.projects import edit_strategy

    baselines = []
    path = root / "stream-baseline-0.sigma"
    view, strategy, credential, config = await setup(path)
    for index in range(2):
        if index:
            path = root / f"stream-baseline-{index}.sigma"
            view, strategy, _, _ = await setup(path)
        research_sessions.save_limits(
            str(path),
            {**research_sessions.DEFAULT_LIMITS, "research_rounds": 1, "model_calls": 4},
        )
        baselines.append((path, view, strategy, str(uuid4())))
    credential = {**credential, "mode": "chatgpt", "identity": "chatgpt:fixture"}
    lanes = [entry[2].id for entry in baselines]
    source_bytes = [entry[0].joinpath("project.json").read_bytes() for entry in baselines]
    tape: list[Exchange] = []
    requests = dict.fromkeys(lanes, 0)
    fixed_time = research_sessions._now()
    lane_counter: ContextVar = ContextVar("replay_lane_counter")

    def deterministic_uuid():
        index, counter = lane_counter.get()
        return UUID(int=(index + 1) * 10_000 + next(counter), version=4)

    def record(request: httpx.Request) -> httpx.Response:
        lane = request_lane(request)
        assert lane in lanes
        index = lanes.index(lane)
        requests[lane] += 1
        ordinal = requests[lane]
        payload = json.loads(request.content)
        assert payload["stream"] is True
        assert request.headers["Accept"] == SSE_TYPE
        context = json.loads(payload["input"][0]["content"])
        role = payload["text"]["format"]["name"]
        assert not context["prior_artifacts"]
        assert not context["prior_session_artifact_ids"]
        assert not context.get("other_strategy_evidence")
        if index == 0 and ordinal == 1:
            exchange = Exchange(
                request_digest(request),
                b'{"error":{"code":"temporary_unavailable"}}',
                503,
                lane=lane,
            )
        else:
            if role == "research_investigator":
                output = investigation(1)
                output["claim"] = f"Synthetic independent strategy {index} consequence."
            else:
                assert role == "research_skeptic"
                output = skeptic(1)
                assert context["investigator_output"]["claim"] == (
                    f"Synthetic independent strategy {index} consequence."
                )
            response_id = f"fixture-{index}-{ordinal}"
            envelope = {**provider_response(output), "id": response_id}
            events = [
                {
                    "type": "response.created",
                    "sequence_number": 0,
                    "response": {"id": response_id},
                },
                {"type": "response.completed", "sequence_number": 1, "response": envelope},
            ]
            body = "".join(
                f"event: {item['type']}\ndata: {json.dumps(item)}\n\n" for item in events
            ).encode()
            exchange = Exchange(
                request_digest(request),
                body,
                content_type=SSE_TYPE,
                lane=lane,
                chunk_sizes=(11, len(body) - 11),
            )
        tape.append(exchange)
        return exchange.make_response()

    async def run(label, handler, *, drift=False):
        seen = set()
        overlapping = asyncio.Event()

        async def overlap(request):
            lane = request_lane(request)
            if lane not in seen:
                seen.add(lane)
                if len(seen) == 2:
                    overlapping.set()
                await asyncio.wait_for(overlapping.wait(), timeout=5)
            return handler(request)

        async def session(index, baseline):
            source, view, strategy, key = baseline
            path = root / f"{label}-{index}.sigma"
            shutil.copytree(source, path)
            if drift and index == 0:
                edit_strategy(
                    path, strategy.id, strategy.title, "A materially different synthetic approach."
                )
            token = lane_counter.set((index, itertools.count(1)))
            try:
                started = await research_sessions.start_session(
                    str(path), strategy.id, key, view.project.id, credential["identity"]
                )
                return await wait_for(path, started["id"])
            finally:
                lane_counter.reset(token)

        with (
            patch.object(research_sessions, "uuid4", side_effect=deterministic_uuid),
            patch.object(research_sessions, "datetime", fixed_scheduler_clock(fixed_time)),
            synthetic_transport(credential, config, overlap),
            fixed_attempt_clock(0.125) as timing_enabled,
        ):
            results = await asyncio.gather(
                *(session(index, item) for index, item in enumerate(baselines))
            )
            session_log.flush()
            for result in results:
                assert_attempt_timing(result, 0.125, enabled=timing_enabled)
        assert overlapping.is_set()
        return results

    original = await run("stream-record", record)
    fixture = root / "synthetic-stream-tape.json"
    fixture.write_bytes(encode_tape(tape))
    loaded = decode_tape(fixture.read_bytes())
    # Global arrival order is irrelevant across lanes; per-strategy order is
    # preserved and strictly checked by exact request digest.
    replay = StrictReplay(
        [item for lane in reversed(lanes) for item in loaded if item.lane == lane]
    )
    repeated = await run("stream-replay", replay)
    replay.assert_complete()
    assert requests == {lanes[0]: 3, lanes[1]: 2}
    assert [item.status for item in loaded if item.lane == lanes[0]] == [503, 200, 200]
    for index, (first, second) in enumerate(zip(original, repeated, strict=True)):
        assert first["status"] == second["status"] == "ended"
        assert first["calls_used"] == second["calls_used"] == (3 if index == 0 else 2)
        assert len(first["artifacts"]) == len(second["artifacts"]) == 1
        assert first["artifacts"][0]["strategy_id"] == lanes[index]
        assert_accepted_equivalence(first, second)
        assert [step["provider_input_audit"]["request_body_sha256"] for step in first["steps"]] == [
            item.request_sha256 for item in loaded if item.lane == lanes[index]
        ]
    assert [step["status"] for step in original[0]["steps"]] == [
        "failed",
        "completed",
        "completed",
    ]
    assert original[0]["steps"][0]["failure_kind"] == "provider_temporary"
    for index, (path, _, _, _) in enumerate(baselines):
        assert path.joinpath("project.json").read_bytes() == source_bytes[index]
        assert not research_sessions.list_sessions(str(path))

    # Run the production scheduler with a deliberately incompatible tape.
    # It must reject the mismatch without delivering any recorded response,
    # and the sticky failure must escape even if the worker catches it.
    incompatible = StrictReplay(loaded)
    try:
        await run("stream-mismatch", incompatible, drift=True)
    except ReplayMismatch as exc:
        assert "Request mismatch" in str(exc)
    else:
        raise AssertionError("Production scheduler concealed a strict request mismatch")
    assert incompatible.failures and incompatible.offsets[lanes[0]] == 0
    print("PASS concurrent strategy lanes, streamed responses, recorded rejection/retry and drift")


async def run_integrations(root: Path) -> None:
    await production_replay(root)
    await parallel_stream_replay(root)


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
            "SIGMA_CLOUD_AUTH_ENABLED": "false",
            "SIGMA_REFERENCE_COMPILATION_ENABLED": "false",
        }
        for name in ("state", "projects", "auth"):
            (root / name).mkdir(mode=0o700)
        with patch.dict(os.environ, env):
            asyncio.run(run_integrations(root / "projects"))


if __name__ == "__main__":
    main()
