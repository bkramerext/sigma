"""Detect runaway JSON formatting whitespace in long-paper streams.

Opt-in only for structured section writing. This lexical state machine works
across SSE text deltas and ignores whitespace inside quoted JSON string values.
It stores neither the generated content nor the original research input.
"""

from __future__ import annotations

from sigma.projects import ProjectError


class JSONWhitespaceStall(ProjectError):
    """The provider emitted an abnormal whitespace-only JSON suffix."""


class JSONWhitespaceGuard:
    """Stop consecutive JSON whitespace outside strings, preserving valid prose."""

    LIMIT = 2048

    def __init__(self, limit: int = LIMIT) -> None:
        if limit <= 0:
            raise ValueError("JSON whitespace limit must be positive")
        self.limit = limit
        self.consecutive = 0
        self.in_string = False
        self.escaped = False

    def observe(self, delta: str) -> None:
        for char in delta:
            if self.in_string:
                if self.escaped:
                    self.escaped = False
                elif char == "\\":
                    self.escaped = True
                elif char == '"':
                    self.in_string = False
                self.consecutive = 0
            elif char == '"':
                self.in_string = True
                self.consecutive = 0
            elif char in " \t\n\r":
                self.consecutive += 1
                if self.consecutive > self.limit:
                    raise JSONWhitespaceStall(
                        "Long-paper section entered a JSON whitespace-output stall. "
                        "The incomplete request was stopped; previously saved sections "
                        "remain intact. No automatic paid retry will occur."
                    )
            else:
                self.consecutive = 0
