"""Render README's Mermaid flow with the independent Mermaid JS library in Chrome."""

import html
import re
from itertools import pairwise
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/evaluations/issue441/readme-mermaid-independent.png"
MERMAID_CDN = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"


def main() -> None:
    readme = (ROOT / "README.md").read_text()
    assert "**[Open Hosted SIGMA →](https://sigma-research.duckdns.org/)**" in readme
    assert readme.index("Open Hosted SIGMA") < readme.index("## Using SIGMA")
    assert "### Workflow" in readme and "### The SIGMA workflow" not in readme
    blocks = re.findall(r"```mermaid\s*\n(.*?)\n```", readme, flags=re.DOTALL)
    assert len(blocks) == 1, f"Expected one inline Mermaid diagram; found {len(blocks)}"
    source = html.escape(blocks[0])
    page_content = f"""<!doctype html>
<html><head><meta charset="utf-8"><style>
body {{ margin: 0; padding: 28px; color: #e5edf5; background: #08111c;
  font: 16px/1.5 system-ui, sans-serif; }}
main {{ box-sizing: border-box; width: min(980px, 100%); margin: auto; padding: 24px;
  border: 1px solid #8d5a43; border-radius: 12px; background: #0c1622; }}
h1 {{ margin: 0 0 20px; color: #efc28a; font-size: 22px; }}
.mermaid {{ margin: 0; }}
</style></head><body><main><h1>SIGMA workflow · independent Mermaid renderer</h1>
<pre class="mermaid">{source}</pre></main>
<script src="{MERMAID_CDN}"></script>
<script>mermaid.initialize({{startOnLoad: true, theme: 'dark', flowchart: {{curve: 'linear'}}}});</script>
</body></html>"""

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            headless=True,
        )
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1100})
            page_errors: list[str] = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.set_content(page_content, wait_until="networkidle", timeout=60000)
            diagram = page.locator(".mermaid svg")
            diagram.wait_for(state="visible", timeout=30000)
            nodes = diagram.locator("g.node")
            labels = [label.strip() for label in nodes.locator(".nodeLabel").all_text_contents()]
            expected_stages = [
                "Project",
                "Strategies",
                "Research",
                "Review and refine",
                "Optional paper",
                "Review and export",
            ]
            normalized_labels = " ".join(" ".join(label.split()) for label in labels)
            assert len(nodes.all()) == 6, normalized_labels
            assert all(stage in normalized_labels for stage in expected_stages), normalized_labels
            edge_count = diagram.locator("path[marker-end]").count()
            assert edge_count == 5, f"Expected five linear flow connectors; found {edge_count}"
            nodes = diagram.locator("g.node")
            centers = nodes.evaluate_all(
                "nodes => nodes.map(n => { const r=n.getBoundingClientRect(); return r.x+r.width/2; })"
            )
            assert all(a < b for a, b in pairwise(centers)), centers
            assert diagram.evaluate("e => e.getBoundingClientRect().width <= 1100"), (
                "Flowchart should fit common desktop widths without excessive scrolling"
            )
            source = blocks[0]
            assert source.lstrip().startswith("flowchart LR"), source[:100]
            assert "-." not in source and "|" not in source, (
                "Flowchart must not contain special/branch edges"
            )
            assert source.count("-->") == 5, source
            assert source.count("[") == source.count("]") == 6, source
            assert "optional" in normalized_labels.lower()
            for explanation in (
                "Export research records and reports for inspection or sharing, with no paper required.",
                "If you create a paper, review its claims, evidence, citations, and limitations before exporting PDF or TeX.",
            ):
                assert explanation in readme, explanation
            assert not page_errors, page_errors
            EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
            page.locator("main").screenshot(path=str(EVIDENCE))
            print(
                f"PASS independent Mermaid JS v11 renderer: six horizontally ordered labels and {edge_count} linear connectors; legible within 1100px."
            )
        finally:
            browser.close()


if __name__ == "__main__":
    main()
