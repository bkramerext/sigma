"""Run disjoint research-session and paper test groups.

Preserve the original explicit test drivers and original test definitions.
The group selector only skips calls directly issued by the research-session
driver; nested test-to-test calls still execute normally. Paper integration
scenarios run in one intact group, without modifying their AST.
"""

from __future__ import annotations

import inspect
import logging
import os
import sys
from contextlib import contextmanager
from collections.abc import Callable
from pathlib import Path
from time import perf_counter
from typing import Any
from unittest.mock import patch

import httpx


_EXPECTED_FAULT_LOGS = {
    "research_sessions": {"session.strategy_exception": 3},
    "papers": {
        "paper.exception": 2,
        "paper.score_failed": 22,
        "paper.section_failed": 6,
    },
}


@contextmanager
def _fixture_logs(suite: str):
    """Capture only known fault-injection diagnostics; reject any new noisy error.

    Keep the complete unexpected record visible if a regression occurs. A changed
    failure-path count requires an explicit review instead of silently turning
    a new runtime error into green CI.
    """
    expected = _EXPECTED_FAULT_LOGS[suite]
    observed: dict[str, int] = {}
    unexpected: list[str] = []
    captured: list[str] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            if record.levelno < logging.WARNING:
                return
            message = self.format(record)
            captured.append(message)
            kind = record.getMessage().partition(" ")[0]
            if kind not in expected:
                unexpected.append(message)
            else:
                observed[kind] = observed.get(kind, 0) + 1

    handler = Capture(level=logging.WARNING)
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
    logger = logging.getLogger()
    logger.addHandler(handler)
    try:
        yield
        excess = {
            kind: (found, expected[kind])
            for kind, found in observed.items()
            if found > expected[kind]
        }
        if unexpected or excess:
            raise AssertionError(
                f"Unreviewed {suite} warning/error logs: {unexpected}; "
                f"fault-injection count over baseline: {excess}"
            )
        if observed:
            summary = ", ".join(f"{key}={value}" for key, value in sorted(observed.items()))
            print(f"PASS expected fault-injection diagnostics captured: {summary}")
    except BaseException:
        for message in captured:
            print(message, file=sys.stderr)
        raise
    finally:
        logger.removeHandler(handler)


def _skip_unselected(name: str, original: Callable[..., Any]) -> Callable[..., Any]:
    """Skip only direct main() calls, retaining nested test helper behavior."""
    async_function = inspect.iscoroutinefunction(original)

    async def skipped_coroutine() -> None:
        return None

    def dispatch(*args: Any, **kwargs: Any) -> Any:
        frame = inspect.currentframe()
        caller = frame.f_back if frame is not None else None
        if caller is not None and caller.f_code.co_name in {"main", "main_part1"}:
            return skipped_coroutine() if async_function else None
        return original(*args, **kwargs)

    dispatch.__name__ = name
    return dispatch


def _time_selected(name: str, original: Callable[..., Any]) -> Callable[..., Any]:
    """Report truly slow scenarios, preserving async test execution and coverage."""
    if inspect.iscoroutinefunction(original):

        async def measured(*args: Any, **kwargs: Any) -> Any:
            start = perf_counter()
            try:
                return await original(*args, **kwargs)
            finally:
                duration = perf_counter() - start
                if duration >= 5:
                    print(f"TEST_DURATION {name} {duration:.1f}s", flush=True)

    else:

        def measured(*args: Any, **kwargs: Any) -> Any:
            start = perf_counter()
            try:
                return original(*args, **kwargs)
            finally:
                duration = perf_counter() - start
                if duration >= 5:
                    print(f"TEST_DURATION {name} {duration:.1f}s", flush=True)

    measured.__name__ = name
    return measured


def run_split(
    name: str, count: int, part: int, *, paper: bool = False, half: int | None = None
) -> None:
    if not 1 <= part <= count:
        raise ValueError(f"Invalid {name} part {part}/{count}")
    directory = Path(__file__).resolve().parent
    namespace: dict[str, Any] = {
        "__name__": f"_{name}_test_definitions",
        "__file__": str(directory / f"{name}.py"),
        "__package__": None,
    }
    assigned: dict[str, int] = {}
    # All definitions need to see the same globals. The original monolithic
    # files provided that property; each group still runs in its own process.
    for number in range(1, count + 1):
        path = directory / f"{name}_part{number}.py"
        source = path.read_text(encoding="utf-8")
        previous = {key: id(value) for key, value in namespace.items()}
        exec(compile(source, str(path), "exec"), namespace)  # noqa: S102
        for key, value in namespace.items():
            if (
                key.startswith("test_")
                and inspect.isfunction(value)
                and id(value) != previous.get(key)
            ):
                assigned[key] = number

    # CI can divide the unusually slow third research-session group into two
    # disjoint processes. Every definition is still executed exactly once, and
    # nested calls to other tests retain their original helper behavior.
    selected_half: set[str] | None = None
    if half is not None:
        if name != "research_sessions" or part != 3 or half not in (1, 2):
            raise ValueError("Only research_sessions part 3 can be divided in half")
        group_names = [key for key, group in assigned.items() if group == part]
        assert len(group_names) >= 2
        selected_half = {
            key for index, key in enumerate(group_names) if index % 2 == half - 1
        }
        assert selected_half and len(selected_half) < len(group_names)

    driver = directory / f"{name}_driver.py"
    exec(compile(driver.read_text(encoding="utf-8"), str(driver), "exec"), namespace)  # noqa: S102
    for key, group in assigned.items():
        if group != part or (selected_half is not None and key not in selected_half):
            namespace[key] = _skip_unselected(key, namespace[key])
        elif os.environ.get("CI"):
            namespace[key] = _time_selected(key, namespace[key])
    assert sum(group == part for group in assigned.values()) > 0
    if not paper:
        with _fixture_logs(name):
            namespace["main"](part)
    else:
        # Preserve the entire former main() integration scenario as one
        # independent unit; the standalone cases run in the other unit.
        papers = namespace["papers"]
        real_client = httpx.AsyncClient

        def offline_async_client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
            if "transport" not in kwargs:
                kwargs["transport"] = httpx.MockTransport(
                    lambda _request: httpx.Response(
                        503,
                        json={"error": {"code": "offline_test_fixture", "message": "offline"}},
                    )
                )
            return real_client(*args, **kwargs)

        httpx.AsyncClient = offline_async_client  # type: ignore[assignment]
        try:
            with (
                _fixture_logs(name),
                patch.object(papers, "_publication_compiler_has_writing_headroom", return_value=False),
            ):
                namespace["main_part1"]()
                if part == 2:
                    namespace["main_part2"]()
        finally:
            httpx.AsyncClient = real_client
    label = f" half {half}/2 ({len(selected_half)} definitions)" if selected_half is not None else ""
    print(f"PASS {name}: part {part}/{count}{label}")


if __name__ == "__main__":
    raise SystemExit("Use the individual *_partN.py entrypoints")
