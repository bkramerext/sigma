"""Focused browser acceptance for project-header hover geometry and click behavior.

Runs under the existing Model Availability browser fixture (API :8001, Vite :5173).
"""

import os
from urllib.parse import urlencode
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

UI = "http://127.0.0.1:5173"
API = "http://127.0.0.1:8001"


def title_geometry(locator):
    return locator.evaluate(
        """button => {
          const box = button.getBoundingClientRect();
          const row = button.closest('.project-header-title-row').getBoundingClientRect();
          const range = document.createRange();
          range.selectNodeContents(button);
          const lines = [...range.getClientRects()].filter(
            rect => rect.width > 0 && rect.top < box.bottom + 1
          );
          return { width: box.width, rowWidth: row.width,
            lines: lines.map(rect => rect.width) };
        }"""
    )


def check_pointer_tooltip(page, title):
    tooltip = page.get_by_role("tooltip")
    expect(tooltip).to_have_text("Toggle all project sections")
    title_box = title.bounding_box()
    tip_box = tooltip.bounding_box()
    assert title_box and tip_box
    # Project titles may occupy a wide header track. Position next to the
    # actual pointer over the text, not the center of the title's hit box.
    expected_left = max(
        8,
        min(page.viewport_size["width"] - tip_box["width"] - 8, title_box["x"] + 12 + 14),
    )
    assert abs(tip_box["x"] - expected_left) <= 4, (title_box, tip_box)
    assert tip_box["y"] >= title_box["y"] + 12 + 12


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=os.environ.get("SIGMA_BROWSER_EXECUTABLE", p.chromium.executable_path),
            headless=True,
        )
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.set_default_timeout(12000)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def forward(route):
            route.fulfill(
                response=route.fetch(
                    url=route.request.url.replace(UI, API),
                    headers={**route.request.headers, "origin": UI},
                )
            )

        page.route("**/api/**", forward)
        page.route(
            "**/api/cloud-auth/status",
            lambda route: route.fulfill(
                json={
                    "target": "local",
                    "enabled": True,
                    "ready": True,
                    "authenticated": True,
                    "user": {"email": "title-hover@example.org", "role": "admin"},
                    "admin_contact_email": None,
                }
            ),
        )
        for name, wrap in [
            ("Title hover " + uuid4().hex[:8], False),
            (
                "Complex regional analysis for a collaborative research project " + uuid4().hex[:8],
                True,
            ),
        ]:
            created = page.request.post(
                API + "/api/projects/create",
                data={"title": name, "problem": "Verify the project header title hover geometry."},
            )
            assert created.status == 201, created.text()
            path = created.json()["path"]
            page.set_viewport_size({"width": 760 if wrap else 1280, "height": 800})
            page.goto(UI + "/project?" + urlencode({"path": path}))
            title = page.get_by_role("button", name="Toggle all project sections")
            expect(title).to_have_text(name)
            page.evaluate("document.fonts.ready")
            if wrap:
                # Find a viewport at which this long title visibly wraps twice;
                # avoid assuming a particular host font's glyph widths.
                for width in (760, 700, 640, 560, 500):
                    page.set_viewport_size({"width": width, "height": 800})
                    page.wait_for_timeout(70)
                    geometry = title_geometry(title)
                    if len(geometry["lines"]) == 2:
                        break
                assert len(geometry["lines"]) == 2, geometry

            title.hover(position={"x": 12, "y": 12})
            expect(title).to_have_css("background-color", "rgb(48, 36, 24)")
            expect(title).to_have_css("text-decoration-line", "none")
            geometry = title_geometry(title)
            assert geometry["lines"], geometry
            assert abs(geometry["width"] - max(geometry["lines"])) <= 6, geometry
            assert geometry["width"] < geometry["rowWidth"] * 0.96, geometry
            check_pointer_tooltip(page, title)
            title.click()
            expect(
                page.locator("#project-pane-heading .workspace-section-disclosure")
            ).to_have_attribute("aria-expanded", "false")
            page.mouse.move(0, 0)
        assert not errors, errors
        browser.close()
        print(
            "PASS project title hover fits text, tooltip follows pointer and click behavior remains"
        )


if __name__ == "__main__":
    main()
