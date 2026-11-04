"""Run disjoint groups from legacy explicit Python test drivers.

Each group loads the same definitions into an isolated interpreter, but executes
only its assigned test statements. No live provider calls are enabled here.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path


def _contains_test_call(node: ast.AST) -> bool:
    return any(
        isinstance(item, ast.Call)
        and isinstance(item.func, ast.Name)
        and item.func.id.startswith("test_")
        for item in ast.walk(node)
    )


class _Partition:
    def __init__(self, part: int, count: int) -> None:
        self.part = part
        self.count = count
        self.total = 0
        self.selected = 0

    def _choose(self) -> bool:
        selected = self.total % self.count == self.part - 1
        self.total += 1
        if selected:
            self.selected += 1
        return selected

    def body(self, body: list[ast.stmt]) -> list[ast.stmt]:
        result: list[ast.stmt] = []
        for stmt in body:
            if isinstance(stmt, ast.Expr) and _contains_test_call(stmt):
                if self._choose():
                    result.append(stmt)
            elif isinstance(stmt, (ast.With, ast.AsyncWith)):
                if _contains_test_call(stmt):
                    stmt.body = self.body(stmt.body)
                    if stmt.body:
                        result.append(stmt)
                elif self._choose():
                    result.append(stmt)
            elif isinstance(stmt, (ast.If, ast.For, ast.AsyncFor, ast.While)):
                if _contains_test_call(stmt):
                    stmt.body = self.body(stmt.body)
                    stmt.orelse = self.body(stmt.orelse)
                    if stmt.body or stmt.orelse:
                        stmt.body = stmt.body or [ast.Pass()]
                        result.append(stmt)
                elif self._choose():
                    result.append(stmt)
            elif isinstance(stmt, ast.Try):
                if _contains_test_call(stmt):
                    stmt.body = self.body(stmt.body)
                    for handler in stmt.handlers:
                        handler.body = self.body(handler.body) or [ast.Pass()]
                    stmt.orelse = self.body(stmt.orelse)
                    stmt.finalbody = self.body(stmt.finalbody)
                    stmt.body = stmt.body or [ast.Pass()]
                    result.append(stmt)
                elif self._choose():
                    result.append(stmt)
            elif isinstance(stmt, ast.Assert):
                if self._choose():
                    result.append(stmt)
            elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                call = stmt.value.func
                # Legacy driver printouts are informational, but other
                # standalone calls are scenarios and must run exactly once.
                if isinstance(call, ast.Name) and call.id == "print":
                    result.append(stmt)
                elif self._choose():
                    result.append(stmt)
            else:
                # Imports and setup assignments are needed by each group.
                result.append(stmt)
        return result


def run_split(name: str, count: int, part: int, *, paper: bool = False) -> None:
    if not 1 <= part <= count:
        raise ValueError(f"Invalid {name} part {part}/{count}")
    directory = Path(__file__).resolve().parent
    globals_dict: dict[str, object] = {
        "__name__": f"_{name}_definitions",
        "__file__": str(directory / f"{name}.py"),
        "__package__": None,
    }
    for number in range(1, count + 1):
        file = directory / f"{name}_part{number}.py"
        exec(compile(file.read_text(encoding="utf-8"), str(file), "exec"), globals_dict)
    driver = directory / f"{name}_driver.py"
    module = ast.parse(driver.read_text(encoding="utf-8"), filename=str(driver))
    main = next(
        node for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    if paper:
        # The old paper driver ends with one cohesive, stateful integration
        # scenario. Keep that block intact; split only at its safe boundary.
        # Part 1 runs all standalone scenarios, part 2 the integration block.
        integration_start = next(
            index for index, node in enumerate(main.body)
            if isinstance(node, ast.With)
            and any(
                isinstance(item.context_expr, ast.Call)
                and isinstance(item.context_expr.func, ast.Name)
                and item.context_expr.func.id == "TemporaryDirectory"
                for item in node.items
            )
        )
        main.body = (
            main.body[:integration_start]
            if part == 1
            else main.body[integration_start:]
        )
        selected = len(main.body)
        total = selected
    else:
        partition = _Partition(part, count)
        main.body = partition.body(main.body)
        selected = partition.selected
        total = partition.total
    ast.fix_missing_locations(module)
    assert selected > 0, (name, part, total)
    exec(compile(module, str(driver), "exec"), globals_dict)
    if paper:
        import httpx
        from unittest.mock import patch

        papers = globals_dict["papers"]
        real_client = httpx.AsyncClient

        def offline_async_client(*args, **kwargs):
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
                globals_dict["main"]()
        finally:
            httpx.AsyncClient = real_client
    else:
        globals_dict["main"]()
    print(f"PASS {name} part {part}/{count}: {selected}/{total} statements")


if __name__ == "__main__":
    raise SystemExit("Use the individual *_partN.py entrypoints")
