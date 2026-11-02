"""Regression coverage for ELI5 paper cache identity."""
from sigma.paper_eli5 import cached


def test_eli5_cache_requires_matching_pdf_sha() -> None:
    record = {
        "pdf_sha256": "a" * 64,
        "eli5": {"source_sha256": "a" * 64, "markdown": "Explanation " * 18},
    }
    assert cached(record) == record["eli5"]["markdown"]
    assert cached({**record, "pdf_sha256": "b" * 64}) is None


def test_eli5_cache_rejects_bad_or_short_content() -> None:
    assert cached({"pdf_sha256": "abc", "eli5": {"source_sha256": "abc", "markdown": "short"}}) is None
    assert cached({"pdf_sha256": "abc", "eli5": {"source_sha256": "abc", "markdown": 123}}) is None
    assert cached({"pdf_sha256": "abc"}) is None
