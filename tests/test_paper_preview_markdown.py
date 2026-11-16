"""Regression contracts for deterministic saved paper title and abstract."""

from __future__ import annotations

from unittest import TestCase

from sigma.paper_preview_markdown import _body_without_front_matter
from sigma.projects import ProjectError


class PaperPreviewMarkdownTests(TestCase):
    def test_preview_excludes_front_matter_from_ai_conversion(self) -> None:
        title = "Maximum Regions"
        abstract = "The maximum count is $1+n(n+1)/2$, including the empty arrangement."
        source = f"{title}\n\nAbstract\n{abstract}\n\nProblem framing\nThe proof follows."
        self.assertEqual(
            _body_without_front_matter(source, title, abstract),
            "Problem framing\nThe proof follows.",
        )

    def test_preview_rejects_mismatched_abstract(self) -> None:
        with self.assertRaisesRegex(ProjectError, "front matter"):
            _body_without_front_matter(
                "Maximum Regions\n\nAbstract\nTruncated\n\nBody",
                "Maximum Regions",
                "Full abstract",
            )
