"""Regression contracts for deterministic paper title/abstract in expanded previews."""

from __future__ import annotations

import pytest

from sigma.paper_preview_markdown import _body_without_front_matter
from sigma.projects import ProjectError


def test_preview_excludes_front_matter_from_ai_conversion() -> None:
    title = "Maximum Regions"
    abstract = "The maximum count is $1+n(n+1)/2$, including the empty arrangement."
    source = f"{title}\n\nAbstract\n{abstract}\n\nProblem framing\nThe proof follows."
    assert _body_without_front_matter(source, title, abstract) == (
        "Problem framing\nThe proof follows."
    )


def test_preview_rejects_dropped_or_mismatched_abstract() -> None:
    with pytest.raises(ProjectError, match="front matter"):
        _body_without_front_matter(
            "Maximum Regions\n\nAbstract\nTruncated\n\nBody", "Maximum Regions", "Full abstract"
        )
