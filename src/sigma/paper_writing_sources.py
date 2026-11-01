"""Select readable writing guidance for papers, separate from research evidence."""

from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser
from typing import Any, Awaitable, Callable, Mapping

import httpx

# Fixed, curated discovery pool. The input project NEVER supplies fetch URLs.
# Add new disciplines and branches here; unavailable pages are skipped.
CATALOG = (
    ("general", "*", "*", "PLOS: Structuring Papers",
     "https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005619"),
    ("general", "*", "*", "PLOS: Writing Research Papers",
     "https://pmc.ncbi.nlm.nih.gov/articles/PMC3907284/"),
    ("discipline", "mathematical", "*", "Tao: On Writing Mathematics",
     "https://terrytao.wordpress.com/advice-on-writing-papers/"),
    ("discipline", "mathematical", "*", "SIAM: Scientific Computing Author Instructions",
     "https://epubs.siam.org/sisc/instructions-for-authors"),
    ("discipline", "physics", "*", "APS: Physics Manuscript Style",
     "https://journals.aps.org/authors/style-basics"),
    ("discipline", "physics", "*", "IOP: Journal Article Structure",
     "https://publishingsupport.iopscience.iop.org/questions/structure-and-format-of-your-journal-article/"),
    ("discipline", "biology", "*", "ARRIVE: Animal Research Reporting",
     "https://arriveguidelines.org/arrive-guidelines"),
    ("discipline", "computer_science", "*", "ACM SIGSOFT: Empirical Standards",
     "https://www2.sigsoft.org/EmpiricalStandards/docs/standards"),
    ("discipline", "engineering", "*", "ACM SIGSOFT: Engineering Research Standards",
     "https://www2.sigsoft.org/EmpiricalStandards/docs/standards"),
    ("discipline", "law", "*", "Stanford Law: Scholarly Writing",
     "https://guides.law.stanford.edu/c.php?g=1255722&p=9200577"),
    ("branch", "mathematical", "combinatorics", "Electronic Journal of Combinatorics: Author Guide",
     "https://www.combinatorics.org/ojs/index.php/eljc/about/submissions"),
    ("branch", "physics", "relativity", "Classical and Quantum Gravity: Author Scope",
     "https://publishingsupport.iopscience.iop.org/journals/classical-and-quantum-gravity/about-classical-quantum-gravity/"),
    ("branch", "biology", "developmental", "ARRIVE: Animal Study Reporting",
     "https://arriveguidelines.org/arrive-guidelines"),
)
_CACHE: dict[str, str | None] = {}


class _Paragraphs(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.in_text = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "nav", "footer", "header", "svg"}:
            self.skip += 1
        if tag in {"p", "li", "h1", "h2", "h3", "h4"} and not self.skip:
            self.in_text += 1
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "li", "h1", "h2", "h3", "h4"} and not self.skip:
            self.in_text = max(0, self.in_text - 1)
        if tag in {"script", "style", "nav", "footer", "header", "svg"}:
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data: str) -> None:
        if self.in_text and not self.skip:
            self.parts.append(data)


def readable(text: str, *, html: bool = False) -> str | None:
    if html:
        parser = _Paragraphs()
        try:
            parser.feed(text)
        except (ValueError, AssertionError):
            return None
        text = " ".join(parser.parts)
    result = re.sub(r"\s+", " ", text).strip()
    if len(result) < 450 or any(
        marker in result[:700].lower()
        for marker in ("access denied", "verify you are human", "captcha required")
    ):
        return None
    return result[:3500]


async def _fetch(url: str) -> str | None:
    if url in _CACHE:
        return _CACHE[url]
    if url not in {item[4] for item in CATALOG}:
        return None
    value = None
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(4.0, connect=2.0), follow_redirects=False
        ) as client:
            response = await client.get(url, headers={"Accept": "text/html"})
            if response.status_code == 200 and len(response.content) <= 220_000:
                kind = response.headers.get("content-type", "")
                if "text/html" in kind:
                    value = readable(response.text, html=True)
                elif "text/plain" in kind:
                    value = readable(response.text)
    except (httpx.HTTPError, UnicodeError, ValueError):
        pass
    _CACHE[url] = value
    return value



def branch_for(project: Mapping[str, Any]) -> str:
    """Conservative branch detection; this classifies writing style, not truth."""
    kind = str(project.get("investigation_type") or "default")
    topic = " ".join(str(project.get(k) or "") for k in ("title", "problem")).lower()
    markers = {
        "mathematical": (
            ("combinatorics", ("subset", "counting", "combinatoric", "generating function", "recurrence")),
        ),
        "physics": (
            ("relativity", ("warp drive", "spacetime", "gravity", "metric", "relativity")),
        ),
        "biology": (
            ("developmental", ("tadpole", "xenopus", "regeneration", "developmental")),
        ),
    }
    for branch, terms in markers.get(kind, ()):
        if any(term in topic for term in terms):
            return branch
    return "general"


def _reusable(items: list[dict[str, Any]], kind: str, branch: str) -> bool:
    if len(items) not in (2, 3):
        return False
    if not all(
        item.get("type") == kind
        and item.get("branch") == branch
        and isinstance(item.get("excerpt"), str)
        and len(item["excerpt"]) >= 450
        and hashlib.sha256(item["excerpt"].encode()).hexdigest() == item.get("sha256")
        for item in items
    ):
        return False
    tiers = {item.get("tier") for item in items}
    has_branch_catalog = any(
        tier == "branch" and category == kind and topic == branch
        for tier, category, topic, _, _ in CATALOG
    )
    return "general" in tiers and (
        "branch" in tiers if has_branch_catalog else "discipline" in tiers
    )


async def select(
    project: Mapping[str, Any],
    previous: list[dict[str, Any]] | None = None,
    *,
    fetch: Callable[[str], Awaitable[str | None]] = _fetch,
) -> tuple[list[dict[str, Any]], str]:
    """Pick readable general / discipline / branch guidance, reusing prior text."""
    kind = str(project.get("investigation_type") or "default")
    branch = branch_for(project)
    if previous and _reusable(previous, kind, branch):
        return previous, "reused"
    items: list[dict[str, Any]] = []
    urls: set[str] = set()
    for tier in ("general", "discipline", "branch"):
        candidates = [
            candidate for candidate in CATALOG
            if candidate[0] == tier
            and (tier == "general" or candidate[1] == kind)
            and (tier != "branch" or candidate[2] == branch)
            and candidate[4] not in urls
        ]
        for _, _, _, title, url in candidates[:2]:
            try:
                # Source selection is not permitted to stall paper planning.
                import asyncio

                body = await asyncio.wait_for(fetch(url), timeout=3.0)
            except (Exception, asyncio.CancelledError):
                body = None
            if not isinstance(body, str):
                continue
            excerpt = readable(body)
            if excerpt is None:
                continue
            items.append({
                "title": title,
                "url": url,
                "tier": tier,
                "type": kind,
                "branch": branch,
                "excerpt": excerpt,
                "sha256": hashlib.sha256(excerpt.encode()).hexdigest(),
            })
            urls.add(url)
            break
    # A field without a specific source still receives a second general guide.
    if len(items) < 2:
        for tier, _, _, title, url in CATALOG:
            if tier != "general" or url in urls:
                continue
            try:
                import asyncio

                body = await asyncio.wait_for(fetch(url), timeout=3.0)
            except (Exception, asyncio.CancelledError):
                continue
            excerpt = readable(body) if isinstance(body, str) else None
            if excerpt:
                items.append({
                    "title": title,
                    "url": url,
                    "tier": "general",
                    "type": kind,
                    "branch": branch,
                    "excerpt": excerpt,
                    "sha256": hashlib.sha256(excerpt.encode()).hexdigest(),
                })
                break
    return items[:3], "selected" if items else "unavailable"


def prompt_material(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Untrusted source prose; usable as writing guidance, not research evidence."""
    return [
        {
            "title": str(item["title"]),
            "url": str(item["url"]),
            "scope": str(item["tier"]),
            "writing_guidance_excerpt": str(item["excerpt"]),
        }
        for item in items[:3]
    ]
