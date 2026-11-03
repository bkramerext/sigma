"""Provider-free pilot admission checks for research-method source retrieval."""

from __future__ import annotations

import hashlib

from sigma.research_method_sources import retrieval_readiness_errors


def source(title: str, *, status: str = "retrieved", reason: str | None = None) -> dict:
    excerpt = f"Verified methodological excerpt for {title}."
    retrieval = {
        "status": status,
        "url": "https://example.org/" + title,
        "content_sha256": hashlib.sha256(excerpt.encode()).hexdigest(),
        "excerpt_sha256": hashlib.sha256(excerpt.encode()).hexdigest(),
        "excerpt": excerpt,
        "reason": reason,
    }
    if status != "retrieved":
        retrieval.update(
            content_sha256=None,
            excerpt_sha256=None,
            excerpt=None,
        )
    return {"title": title, "url": retrieval["url"], "retrieval": retrieval}


def main() -> None:
    retrieved = [source("UConn"), source("Close-reading"), source("Source-synthesis")]
    assert retrieval_readiness_errors({"sources": retrieved}) == []

    # Exactly the Crucible failure pattern: 3 selected sources, only 1 inspected.
    unavailable = [
        retrieved[0],
        source("Close-reading", status="unavailable", reason="http_403"),
        source("Source-synthesis", status="unavailable", reason="http_403"),
    ]
    issues = retrieval_readiness_errors({"sources": unavailable})
    assert len(issues) == 2
    assert all("http_403" in item for item in issues)
    assert any("Close-reading" in item for item in issues)
    assert any("Source-synthesis" in item for item in issues)

    # A title, URL, or coordinator annotation never counts as source content.
    metadata_only = {"title": "Uninspected", "url": "https://example.org/uninspected"}
    assert len(retrieval_readiness_errors({"sources": [metadata_only]})) == 1

    # Tampered saved content cannot masquerade as a verified excerpt.
    modified = source("Tampered")
    modified["retrieval"]["excerpt"] = "Different text"
    assert "SHA-256" in retrieval_readiness_errors({"sources": [modified]})[0]
    missing_content_hash = source("No-content-hash")
    missing_content_hash["retrieval"]["content_sha256"] = None
    assert "source-content SHA-256" in retrieval_readiness_errors(
        {"sources": [missing_content_hash]}
    )[0]

    # An empty selection is not evidence that all configured methods were read.
    assert retrieval_readiness_errors({"sources": []})
    assert retrieval_readiness_errors({"sources": "invalid"})
    print("PASS: research-reference strict admission / all-3 retrievable / 403 / provenance")


if __name__ == "__main__":
    main()
