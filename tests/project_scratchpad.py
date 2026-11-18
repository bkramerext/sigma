"""Project Scratchpad portability and edit collision regression tests."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from sigma.projects import (
    ProjectError,
    _decode,
    _document,
    _validate_scratchpad,
    initialize_project,
    inspect_project,
    update_project_scratchpad,
)


def test_scratchpad_saved_in_project_document_and_survives_reopen() -> None:
    with TemporaryDirectory() as directory:
        path = Path(directory) / "scratchpad.sigma"
        initialize_project(path, "Scratchpad test", "A research objective")
        first = {"id": "a" * 32, "text": "An idea with **Markdown** and $x^2$"}
        second = {"id": "b" * 32, "text": ""}
        view = update_project_scratchpad(path, [first, second], [])
        assert list(view.project.scratchpad) == [first, second]
        saved = inspect_project(path).project
        assert list(saved.scratchpad) == [first, second]
        assert list(_decode(json.loads(_document(saved))).scratchpad) == [first, second]


def test_scratchpad_rejects_conflicting_edits_without_discarding_notes() -> None:
    with TemporaryDirectory() as directory:
        path = Path(directory) / "scratchpad.sigma"
        initialize_project(path, "Scratchpad test", "A research objective")
        entry = {"id": "c" * 32, "text": "First writer"}
        update_project_scratchpad(path, [entry], [])
        try:
            update_project_scratchpad(path, [{"id": "d" * 32, "text": "Second writer"}], [])
        except ProjectError as exc:
            assert "changed elsewhere" in str(exc)
        else:
            raise AssertionError("Stale Scratchpad update overwrote the first writer")
        assert list(inspect_project(path).project.scratchpad) == [entry]


def test_scratchpad_rejects_invalid_notes() -> None:
    invalid_entries = [
        [{"id": "x" * 32, "text": "Invalid ID"}],
        [{"id": "a" * 32, "text": "A"}, {"id": "a" * 32, "text": "duplicate"}],
        [{"id": "a" * 32, "text": "x" * 50001}],
        [{"id": "a" * 32, "text": "ok", "extra": "not allowed"}],
        [{"id": "a" * 32, "text": "ok"}] * 101,
    ]
    for entries in invalid_entries:
        try:
            _validate_scratchpad(entries)
        except ProjectError:
            pass
        else:
            raise AssertionError("Invalid Scratchpad entry was accepted")
