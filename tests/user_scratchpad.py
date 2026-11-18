"""User Scratchpad persistence and collision regression checks."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sigma import research_preferences, user_scratchpad
from sigma.projects import ProjectError


def test_user_scratchpad_persists_without_project_file() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        with patch.object(research_preferences, "_root", return_value=root):
            assert user_scratchpad.current() == {"entries": []}
            entry = {"id": "a" * 32, "text": "**Note** about $x^2$"}
            assert user_scratchpad.save([entry], []) == {"entries": [entry]}
            assert user_scratchpad.current() == {"entries": [entry]}
            data = json.loads((root / user_scratchpad.FILENAME).read_text())
            assert data["entries"] == [entry]
            try:
                user_scratchpad.save([], [])
            except ProjectError as exc:
                assert "changed elsewhere" in str(exc)
            else:
                raise AssertionError("Stale user Scratchpad edit overwrote saved notes")
            assert user_scratchpad.current() == {"entries": [entry]}


def test_user_scratchpad_rejects_invalid_notes() -> None:
    invalid = [
        [{"id": "x" * 32, "text": "Invalid ID"}],
        [{"id": "a" * 32, "text": "A"}, {"id": "a" * 32, "text": "duplicate"}],
        [{"id": "a" * 32, "text": "x" * 50001}],
        [{"id": "a" * 32, "text": "ok", "extra": "not allowed"}],
        [{"id": "a" * 32, "text": "ok"}] * 101,
    ]
    for entries in invalid:
        try:
            user_scratchpad._validate(entries)
        except ProjectError:
            pass
        else:
            raise AssertionError("Invalid Scratchpad entry accepted")
