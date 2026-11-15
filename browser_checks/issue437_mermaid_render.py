"""Render README's Mermaid flow with the independent Mermaid JS library in Chrome."""

import html
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/evaluations/issue437/readme-mermaid-independent.png"
MERMAID_CDN = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"


def main() -> None:
    readme = (ROOT / "README.md").read_text()
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
                "Create a project",
                "Explore research strategies",
                "Run Investigator and Skeptic research",
                "Review findings and refine understanding",
                "Draft an academic paper",
                "Review and export",
            ]
            normalized_labels = " ".join(" ".join(label.split()) for label in labels)
            assert len(nodes.all()) == 6, normalized_labels
            assert all(stage in normalized_labels for stage in expected_stages), normalized_labels
            edge_count = diagram.locator("path[marker-end]").count()
            assert edge_count >= 6, f"Expected six visible flow connectors; found {edge_count}"
            edge_labels = " ".join(diagram.locator(".edgeLabel").all_text_contents())
            assert "optional paper" in edge_labels.lower(), edge_labels
            assert "research records and reports" in edge_labels.lower(), edge_labels
            assert "paper review and export" in edge_labels.lower(), edge_labels
            assert not page_errors, page_errors
            EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
            page.locator("main").screenshot(path=str(EVIDENCE))
            print(
                f"PASS independent Mermaid JS v11 renderer: 6 labeled stages, {edge_count} connectors, optional-paper and distinct research/paper export paths."
            )
        finally:
            browser.close()


if __name__ == "__main__":
    main()
