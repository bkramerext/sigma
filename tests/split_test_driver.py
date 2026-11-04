"""Run disjoint research-session and paper test groups.

Preserve the original explicit test drivers and original test definitions.
The group selector only skips calls directly issued by the research-session
driver; nested test-to-test calls still execute normally. Paper integration
scenarios run in one intact group, without modifying their AST.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, Callable


def _skip_unselected(name: str, original: Callable[..., Any]) -> Callable[..., Any]:
    """Skip only direct main() calls, retaining nested test helper behavior."""
    async_function = inspect.iscoroutinefunction(original)

    async def skipped_coroutine() -> None:
        return None

    def dispatch(*args: Any, **kwargs: Any) -> Any:
        frame = inspect.currentframe()
        caller = frame.f_back if frame is not None else None
        if caller is not None and caller.f_code.co_name == "main":
            return skipped_coroutine() if async_function else None
        return original(*args, **kwargs)

    dispatch.__name__ = name
    return dispatch


def run_split(name: str, count: int, part: int, *, paper: bool = False) -> None:
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
        exec(compile(source, str(path), "exec"), namespace)
        for key, value in namespace.items():
            if (
                key.startswith("test_")
                and inspect.isfunction(value)
                and id(value) != previous.get(key)
            ):
                assigned[key] = number

    driver = directory / f"{name}_driver.py"
    exec(compile(driver.read_text(encoding="utf-8"), str(driver), "exec"), namespace)
    if not paper:
        for key, group in assigned.items():
            if group != part:
                namespace[key] = _skip_unselected(key, namespace[key])
        assert sum(group == part for group in assigned.values()) > 0
        namespace["main"](part)
    else:
        # Preserve the entire former main() integration scenario as one
        # independent unit; the standalone cases run in the other unit.
        import httpx
        from unittest.mock import patch

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
            with patch.object(
                papers, "_publication_compiler_has_writing_headroom", return_value=False
            ):
                namespace[f"main_part{part}"]()
        finally:
            httpx.AsyncClient = real_client
    print(f"PASS {name}: part {part}/{count}")


if __name__ == "__main__":
    raise SystemExit("Use the individual *_partN.py entrypoints")
