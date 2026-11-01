"""Real Chrome acceptance for saved AI paper actions, rendering and removal."""

import json
import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import expect, sync_playwright

REPO = Path(__file__).resolve().parents[1]
ARCHIVE = (
    REPO
    / "docs/evaluations/fixtures/t17-8-answer-free/live-session-91e96112-27ce-412e-841f-5cbf67cbba75.json"
)
CHROME = os.environ.get(
    "SIGMA_BROWSER_EXECUTABLE", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
)


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def wait_for(url: str, process: subprocess.Popen) -> None:
    import urllib.error
    import urllib.request

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(f"Isolated server exited with status {process.returncode}")
        try:
            with urllib.request.urlopen(url, timeout=1):
                return
        except (OSError, urllib.error.URLError):
            time.sleep(0.1)
    raise AssertionError(f"Isolated server did not become ready: {url}")


with tempfile.TemporaryDirectory(prefix="sigma-t125-browser-") as temporary:
    root = Path(temporary)
    project_path = root / "paper-project.sigma"
    sessions_path = project_path / "research-sessions"
    sessions_path.mkdir(parents=True)
    export = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    project = export["project"]
    project_id = project["id"]
    (project_path / "project.json").write_text(json.dumps(project), encoding="utf-8")

    from sigma import papers

    tex_source = r"\documentclass{article}\begin{document}Saved paper fixture.\end{document}"
    pdf_bytes = papers._compile_pdf(tex_source)
    identifiers = ["a" * 32, "b" * 32]
    for index, paper_id in enumerate(identifiers):
        hostile = (
            "<script>window.__paperXss = true</script>" if index == 0 else "A second saved paper."
        )
        papers._save(
            str(project_path),
            {
                "paper_id": paper_id,
                "project_id": project_id,
                "created_at": f"2026-10-2{5 - index}T12:00:00+00:00",
                "snapshot_sha256": "c" * 64,
                "snapshot": {"sources": [{"id": "fixture-source", "kind": "session"}]},
                "draft": {
                    "title": f"Saved fixture {index + 1}",
                    "abstract": hostile,
                    "abstract_claim_ids": [],
                    "problem_framing": ["The original problem is retained."],
                    "problem_framing_claim_ids": [],
                    "methods": ["Saved evidence was reviewed."],
                    "methods_claim_ids": [],
                    "claims": [],
                    "sections": [
                        {"heading": "Saved section", "paragraphs": [hostile], "claim_ids": []}
                    ],
                    "limitations": ["This fixture is not a mathematical result."],
                    "open_obligations": ["Review the saved argument."],
                    "conclusions": ["No independent verification is implied."],
                    "conclusion_claim_ids": [],
                },
                "tex_source": tex_source,
                "validation_warnings": [],
                "author_review_warnings": [],
                "obligation_reconciliation": [],
                "generation": {
                    "mode": "api_key",
                    "model": "test-fixture",
                    "reasoning_effort": "low",
                    "call_limit": 2,
                    "provider_calls_attempted": 0,
                },
            },
            pdf_bytes,
        )

    api_port, ui_port = free_port(), free_port()
    while api_port == ui_port:
        ui_port = free_port()
    api_url, ui_url = f"http://127.0.0.1:{api_port}", f"http://127.0.0.1:{ui_port}"
    environment = os.environ.copy()
    environment["SIGMA_PROJECTS_ROOT"] = str(root)
    api = subprocess.Popen(
        [
            "uv",
            "run",
            "--project",
            str(REPO),
            "python",
            "-m",
            "uvicorn",
            "sigma.server:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(api_port),
        ],
        cwd=REPO,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    environment["SIGMA_API_TARGET"] = api_url
    ui = subprocess.Popen(
        [
            "npm",
            "--prefix",
            str(REPO / "frontend"),
            "run",
            "dev",
            "--",
            "--host",
            "127.0.0.1",
            "--port",
            str(ui_port),
        ],
        cwd=REPO,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_for(api_url + "/openapi.json", api)
        wait_for(ui_url, ui)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=CHROME, headless=True, args=["--disable-web-security"]
            )
            context = browser.new_context(
                viewport={"width": 1440, "height": 1000}, accept_downloads=True
            )
            page = context.new_page()
            page_errors: list[str] = []
            generation_posts: list[str] = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.on(
                "request",
                lambda request: (
                    generation_posts.append(request.url)
                    if request.method == "POST" and request.url.endswith("/api/projects/papers")
                    else None
                ),
            )
            target = f"{ui_url}/project?path={quote(str(project_path), safe='')}"
            page.goto(target)
            page.get_by_role("button", name="LaTeX research paper").click()
            dialog = page.get_by_role("dialog", name="Academic paper using LaTeX")
            expect(dialog).to_be_visible()
            row = dialog.locator(f'article.saved-paper-card[data-paper-id="{identifiers[0]}"]')
            expect(row.locator(".saved-paper-title-toggle")).to_be_visible()
            expect(row).to_contain_text("Version 1")
            expected_basename = papers.paper_download_basename(str(project_path), identifiers[0])
            expect(row.get_by_role("link", name="Download text file")).to_be_visible()
            expect(row.get_by_role("link", name="Download PDF")).to_be_visible()
            open_link = row.get_by_role("link", name="Open PDF in browser")
            expect(open_link).to_have_attribute("target", "_blank")
            preview = row.locator(".ai-paper-preview")
            expect(preview).to_be_hidden()
            row.locator("button.saved-paper-expand").click()
            expect(preview).to_be_visible()
            expect(preview).to_contain_text("Saved section")
            expect(preview).to_contain_text("<script>window.__paperXss = true</script>")
            assert preview.locator("script, img").count() == 0
            assert page.evaluate("window.__paperXss ?? false") is False

            with page.expect_download() as download_info:
                row.get_by_role("link", name="Download text file").click()
            text_download = download_info.value
            assert text_download.suggested_filename == f"{expected_basename}.txt"
            text_disposition = page.evaluate(
                "async href => (await fetch(href)).headers.get('content-disposition')",
                row.get_by_role("link", name="Download text file").get_attribute("href"),
            )
            assert (
                f"filename*=UTF-8''{quote(f'{expected_basename}.txt', safe='')}" in text_disposition
            )
            text_content = Path(text_download.path()).read_text(encoding="utf-8")
            assert (
                "Saved fixture 1" in text_content
                and "<script>window.__paperXss = true</script>" in text_content
            )

            with page.expect_download() as download_info:
                row.get_by_role("link", name="Download PDF").click()
            pdf_download = download_info.value
            assert pdf_download.suggested_filename == f"{expected_basename}.pdf"
            pdf_disposition = page.evaluate(
                "async href => (await fetch(href)).headers.get('content-disposition')",
                row.get_by_role("link", name="Download PDF").get_attribute("href"),
            )
            assert (
                f"filename*=UTF-8''{quote(f'{expected_basename}.pdf', safe='')}" in pdf_disposition
            )
            assert Path(pdf_download.path()).read_bytes() == pdf_bytes

            with page.expect_download() as download_info:
                row.get_by_role("link", name="Download TeX file").click()
            tex_download = download_info.value
            assert tex_download.suggested_filename == f"{expected_basename}.tex"
            tex_disposition = page.evaluate(
                "async href => (await fetch(href)).headers.get('content-disposition')",
                row.get_by_role("link", name="Download TeX file").get_attribute("href"),
            )
            assert (
                f"filename*=UTF-8''{quote(f'{expected_basename}.tex', safe='')}" in tex_disposition
            )

            with page.expect_popup() as page_info:
                open_link.click()
            pdf_tab = page_info.value
            pdf_tab.wait_for_load_state("domcontentloaded")
            assert "open_in_browser=true" in pdf_tab.url, pdf_tab.url
            import urllib.request

            with urllib.request.urlopen(pdf_tab.url, timeout=10) as pdf_response:
                assert pdf_response.headers.get_content_type() == "application/pdf"
                assert "inline" in pdf_response.headers.get("Content-Disposition", "")
                assert (
                    f"filename*=UTF-8''{quote(f'{expected_basename}.pdf', safe='')}"
                    in pdf_response.headers.get("Content-Disposition", "")
                )
                assert pdf_response.read() == pdf_bytes
            pdf_tab.close()

            row.get_by_role("button", name="Remove").click()
            confirmation = row.get_by_role("group", name="Confirm removal of Saved fixture 1")
            expect(confirmation).to_be_visible()
            expect(confirmation).to_contain_text("Other versions and research history will remain")
            confirmation.get_by_role("button", name="Cancel").click()
            expect(row).to_be_visible()
            row.get_by_role("button", name="Remove").click()
            row.get_by_role("group", name="Confirm removal of Saved fixture 1").get_by_role(
                "button", name="Confirm", exact=True
            ).click()
            expect(
                dialog.locator(f'article.saved-paper-card[data-paper-id="{identifiers[0]}"]')
            ).to_have_count(0)
            expect(
                dialog.locator(f'article.saved-paper-card[data-paper-id="{identifiers[1]}"]')
            ).to_have_count(1)
            assert not (project_path / "papers" / f"{identifiers[0]}.json").exists()
            assert not (project_path / "papers" / f"{identifiers[0]}.pdf").exists()
            assert (project_path / "papers" / f"{identifiers[1]}.json").exists()
            assert (project_path / "papers" / f"{identifiers[1]}.pdf").exists()

            page.set_viewport_size({"width": 390, "height": 844})
            second_row = dialog.locator(
                f'article.saved-paper-card[data-paper-id="{identifiers[1]}"]'
            )
            expect(second_row).to_contain_text("Version 2")
            second_basename = papers.paper_download_basename(str(project_path), identifiers[1])
            expect(second_row.get_by_role("link", name="Download text file")).to_have_attribute(
                "download", f"{second_basename}.txt"
            )
            expect(second_row.get_by_role("link", name="Download text file")).to_be_visible()
            expect(second_row.get_by_role("link", name="Open PDF in browser")).to_be_visible()
            expect(
                dialog.locator(f'article.saved-paper-card[data-paper-id="{identifiers[0]}"]')
            ).to_have_count(0)
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            page.screenshot(path="/tmp/sigma-t125-paper-library-mobile.png", full_page=True)
            assert not generation_posts, generation_posts
            assert not page_errors, page_errors
            browser.close()
    finally:
        ui.terminate()
        api.terminate()
        ui.wait(timeout=10)
        api.wait(timeout=10)

print(
    "T125 real Chrome saved-paper text/PDF downloads, escaped preview, confirmation, removal, and mobile checks passed"
)
