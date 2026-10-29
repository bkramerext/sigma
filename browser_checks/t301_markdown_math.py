"""Exercise SIGMA's real Markdown component in Chrome with math/prose fixtures."""

import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE_URL = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5193")
BODY = (
    Path("docs/evaluations/t301/markdown-regression-output.md").read_text(encoding="utf-8").rstrip()
)
RAW_BODY = r"""The probability is 1/2. We obtain f(x) = x² + 3x and E = mc². The roots satisfy x = (-b ± √(b²-4ac))/(2a). The sequence has terms a_n = a_(n-1) + d. The value of x_i is stored in MAX_RETRY_COUNT. The fraction is (a+b)/(c+d). Inline `MAX_RETRY_COUNT` and fenced code remain literal.

```python
MAX_RETRY_COUNT = 3
```"""


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    page = browser.new_page(viewport={"width": 1100, "height": 1100}, device_scale_factor=1)
    page.goto(BASE_URL, wait_until="networkidle")
    page.evaluate(
        """async body => {
          const React = (await import('/node_modules/.vite/deps/react.js')).default;
          const { createRoot } = (await import('/node_modules/.vite/deps/react-dom_client.js')).default;
          const { default: RenderedMarkdown } = await import('/src/RenderedMarkdown.tsx');
          const host = document.createElement('main');
          host.id = 't301-math-regression';
          host.style.cssText = 'max-width:900px;margin:30px auto;padding:28px;background:#fff;color:#222;font:17px/1.7 Georgia,serif';
          document.body.replaceChildren(host);
          createRoot(host).render(React.createElement(RenderedMarkdown, { body }));
        }""",
        BODY,
    )
    root = page.locator("#t301-math-regression")
    expect(root.locator(".katex")).to_have_count(20)
    math_tex = root.locator(".katex").evaluate_all(
        "nodes => nodes.map(node => node.querySelector('annotation')?.textContent || '')"
    )
    for expression in (
        r"\frac{1}{2}",
        "f(x) = x^2 + 3x",
        "E = mc^2",
        r"x = \frac{-b \pm \sqrt{b^2-4ac}}{2a}",
        "a_n = a_{n-1} + d",
        r"\frac{a+b}{c+d}",
        r"\frac{x^2+1}{2x}",
    ):
        assert expression in math_tex, f"Missing expected typeset expression: {expression}"
    assert not any("MAX_RETRY_COUNT" in expression for expression in math_tex)
    assert not any("DATABASE_URL" in expression for expression in math_tex)
    expect(root.locator("table")).to_be_visible()
    expect(root.locator("table tbody tr").nth(0).locator(".katex")).to_have_count(1)
    expect(root.locator("em")).to_contain_text("An emphasized value")
    expect(root.locator("li li .katex")).to_have_count(2)
    expect(root.locator("code")).to_have_count(5)
    expect(root.locator("pre code")).to_contain_text("MAX_RETRY_COUNT = 3")
    expect(root).to_contain_text("MAX_RETRY_COUNT")
    expect(root).to_contain_text("SIGMA_CLOUD_ADMIN_CONTACT_EMAIL")
    expect(root).to_contain_text("DATABASE_URL")
    expect(root).to_contain_text("2026/10/28")
    expect(root).to_contain_text("v1/2")
    expect(root).to_contain_text("/var/data/a_b")
    expect(root).to_contain_text("https://example.com/a_b")
    expect(root).to_contain_text("$5")
    expect(root.locator(".katex").filter(has_text="MAX_RETRY_COUNT")).to_have_count(0)
    expect(root.locator(".katex").filter(has_text="DATABASE_URL")).to_have_count(0)
    expect(root.locator(".katex").filter(has_text="2026")).to_have_count(0)
    page.screenshot(path="docs/evaluations/t301/markdown-render.png", full_page=True)

    page.evaluate(
        """async body => {
          const React = (await import('/node_modules/.vite/deps/react.js')).default;
          const { createRoot } = (await import('/node_modules/.vite/deps/react-dom_client.js')).default;
          const { default: RenderedMarkdown } = await import('/src/RenderedMarkdown.tsx');
          const host = document.createElement('main');
          host.id = 't301-raw-math-regression';
          host.style.cssText = 'max-width:900px;margin:30px auto;padding:28px;background:#fff;color:#222;font:17px/1.7 Georgia,serif';
          document.body.append(host);
          createRoot(host).render(React.createElement(RenderedMarkdown, { body }));
        }""",
        RAW_BODY,
    )
    raw = page.locator("#t301-raw-math-regression")
    expect(raw.locator(".katex")).to_have_count(7)
    raw_tex = raw.locator(".katex").evaluate_all(
        "nodes => nodes.map(node => node.querySelector('annotation')?.textContent || '')"
    )
    for expression in (
        r"\frac{1}{2}",
        "f(x) = x^{2} + 3x",
        "E = mc^{2}",
        r"x = \frac{-b \pm \sqrt{b^{2}-4ac}}{2a}",
        r"a_n = a_{n-1} + d",
        "x_i",
        r"\frac{a+b}{c+d}",
    ):
        assert expression in raw_tex, f"Bare notation was not recognized: {expression}"
    expect(raw).to_contain_text("MAX_RETRY_COUNT")
    expect(raw.locator(".katex").filter(has_text="MAX_RETRY_COUNT")).to_have_count(0)
    expect(raw.locator("code")).to_have_count(2)
    page.screenshot(path="docs/evaluations/t301/markdown-render-raw-math.png", full_page=True)
    browser.close()

print(
    "PASS real Chrome rendered conversion fixture and recognized bare math with semantic preservation"
)
