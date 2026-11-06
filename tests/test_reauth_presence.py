"""Provider-free tests for workspace-scoped continuity through SIGMA reauthentication."""

from __future__ import annotations

import os
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sigma import research_presence
from sigma.projects import initialize_project


def test_workspace_presence_and_explicit_signout_handoff() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        owner = root / "owner"
        other = root / "other"
        owner.mkdir()
        other.mkdir()
        first = owner / "first.sigma"
        second = owner / "second.sigma"
        foreign = other / "foreign.sigma"
        for path in (first, second, foreign):
            initialize_project(path, path.stem, "Research an independent question.")
        with patch.object(research_presence, "projects_root", return_value=owner):
            assert not research_presence.has_live_viewer(str(first))
            assert not research_presence.has_live_viewer(str(second))
            viewer = research_presence.open_workspace_viewer()
            try:
                assert research_presence.has_live_viewer(str(first))
                assert research_presence.has_live_viewer(str(second))
                assert not research_presence.has_live_viewer(str(foreign))
            finally:
                research_presence.close_viewer(viewer)
            assert not research_presence.has_live_viewer(str(first))
            research_presence.refresh_workspace_viewer("00000000-0000-4000-8000-000000000001")
            assert research_presence.has_live_viewer(str(first))
            assert research_presence.has_live_viewer(str(second))
            leased = (
                owner
                / research_presence.DIRECTORY
                / "workspace-00000000-0000-4000-8000-000000000001.viewer"
            )
            leased.unlink()
            assert not research_presence.has_live_viewer(str(first))
            research_presence.begin_auth_handoff()
            assert research_presence.has_live_viewer(str(first))
            assert research_presence.has_live_viewer(str(second))
            assert not research_presence.has_live_viewer(str(foreign))
            # A generic disconnection cannot extend an expired sign-out lease.
            marker = owner / research_presence.DIRECTORY / research_presence.AUTH_HANDOFF_MARKER
            expired = time.time() - research_presence.AUTH_HANDOFF_SECONDS - 5
            os.utime(marker, (expired, expired))
            assert not research_presence.has_live_viewer(str(first))
            assert not research_presence.has_live_viewer(str(second))
            # A genuine authenticated re-sign-in creates a new live workspace lease.
            reattached = research_presence.open_workspace_viewer()
            try:
                assert research_presence.has_live_viewer(str(first))
                assert research_presence.has_live_viewer(str(second))
            finally:
                research_presence.close_viewer(reattached)
