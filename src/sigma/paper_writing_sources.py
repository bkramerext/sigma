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

