"""Real Chrome SIWC workflow against explicit no-network signed OAuth fixture."""

import json
import os
from contextlib import suppress
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import expect, sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    errors = []
    authorization = {"declined": False, "hold": False, "held": []}
    context.on("page", lambda page: page.on("pageerror", lambda error: errors.append(str(error))))

    def api(route):
        response = route.fetch(
            url=route.request.url.replace("127.0.0.1:5173", "127.0.0.1:8001"), max_redirects=0
        )
        if "/api/ai/auth/open/" in route.request.url and response.status == 307:
            trusted = response.headers["location"]
            assert trusted.startswith("https://auth.openai.com/api/accounts/authorize?")
            if authorization["hold"]:
                authorization["held"].append(route)
                return
            authorized = context.request.post(
                "http://127.0.0.1:8001/__fixture__/authorize",
                data={"url": trusted, "declined": authorization["declined"]},
            )
            assert authorized.ok
            route.fulfill(status=302, headers={"Location": authorized.json()["callback"]}, body="")
        else:
            route.fulfill(response=response)

    context.route("http://127.0.0.1:5173/api/**", api)
    context.route("https://auth.openai.com/**", lambda route: route.abort())

    page = context.new_page()
    page.set_default_timeout(10000)

    def stats():
        return context.request.get("http://127.0.0.1:8001/__fixture__/stats").json()

    def control(state):
        assert context.request.post(
            "http://127.0.0.1:8001/__fixture__/state", data={"state": state}
        ).ok

    page.goto("http://127.0.0.1:5173/")
    expect(page.get_by_role("status").filter(has_text="Connect AI")).to_be_visible()
    assert stats()["generated"] == 0
    page.get_by_role("button", name="New Project", exact=True).click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label("Project name", exact=True).fill("SIWC browser " + uuid4().hex[:8])
    dialog.get_by_label("Research problem", exact=True).fill(
        "Compare necessary moment constraints without claiming a proof."
    )
    dialog.get_by_role("button", name="New Project", exact=True).click()
    expect(page.get_by_role("heading", name="Strategies", exact=True)).to_be_visible()
    path = Path(parse_qs(urlsplit(page.url).query)["path"][0])
    page.get_by_title("Write manually", exact=True).click()
    page.get_by_label("Title", exact=True).fill("Manual without account")
    page.get_by_label("Hypothesis / approach", exact=True).fill(
        "Start from human-authored research without authentication."
    )
    page.get_by_role("button", name="Save strategy", exact=True).click()
    expect(page.get_by_role("heading", name="Manual without account", exact=True)).to_be_visible()
    assert stats()["generated"] == 0
    before = (path / "project.json").read_bytes()

    def open_generate():
        page.get_by_label("New Strategy options", exact=True).click()
        page.get_by_role("button", name="Generate with AI", exact=True).click()
        return page.get_by_role("dialog")

    dialog = open_generate()
    dialog.get_by_label("Starting point", exact=False).fill(
        "Preserve this nonempty seed through sign-in"
    )
    # Cancel one owned OAuth attempt without losing the dialog seed or sending data.
    authorization["hold"] = True
    dialog.get_by_role("button", name="Continue with ChatGPT", exact=True).click()
    expect(dialog.get_by_role("button", name="Cancel sign-in", exact=True)).to_be_visible()
    dialog.get_by_role("button", name="Cancel sign-in", exact=True).click()
    expect(dialog.get_by_role("button", name="Continue with ChatGPT", exact=True)).to_be_enabled()
    expect(dialog.get_by_label("Starting point", exact=False)).to_have_value(
        "Preserve this nonempty seed through sign-in"
    )
    assert stats()["generated"] == 0
    for held in authorization["held"]:
        with suppress(PlaywrightError):
            held.abort()
    authorization["hold"], authorization["held"] = False, []
    # A declined login is retryable in place, without clearing seed or generating.
    authorization["declined"] = True
    dialog.get_by_role("button", name="Continue with ChatGPT", exact=True).click()
    expect(dialog.get_by_role("alert").filter(has_text="declined")).to_be_visible()
    assert stats()["generated"] == 0
    authorization["declined"] = False
    dialog.get_by_role("button", name="Continue with ChatGPT", exact=True).click()
    expect(dialog.get_by_label("Title", exact=True)).to_have_value(
        "A finite moment obstruction", timeout=20000
    )
    assert stats()["generated"] == 1
    sent = stats()["last_input"]
    assert (
        json.loads(sent[0]["content"])["starting_point"]
        == "Preserve this nonempty seed through sign-in"
    )
    assert (path / "project.json").read_bytes() == before
    expect(dialog.get_by_text("You're using your ChatGPT plan", exact=True)).to_be_visible()
    dialog.get_by_role("button", name="Got it", exact=True).click()
    dialog.get_by_label("Title", exact=True).fill("Human acceptance after verified plan flow")
    dialog.get_by_role("button", name="Save strategy", exact=True).click()
    expect(
        page.get_by_role("heading", name="Human acceptance after verified plan flow", exact=True)
    ).to_be_visible()
    assert stats()["generated"] == 1
    saved = json.loads((path / "project.json").read_text())
    assert len(saved["strategies"]) == 2 and saved["schema_version"] == 6
    assert saved["strategies"][-1]["provenance"]["model"] == "gpt-6.1-sol-fixture-returned"
    assert "access_token" not in json.dumps(saved)
    page.reload()
    expect(page.get_by_role("status").filter(has_text="ChatGPT connected")).to_be_visible()
    assert not page.get_by_text("You're using your ChatGPT plan", exact=True).count()
    assert stats()["generated"] == 1
    print(
        "PASS no-key manual work, cancelled/declined on-demand OAuth keeps seed, signed callback resumes exactly one SSE proposal, one explicit human save, welcome once and no generation on reload"
    )

    page.get_by_label("AI connection settings", exact=True).click()
    popover = page.locator(".connection-details")
    expect(popover.get_by_text("Using ChatGPT plan", exact=True)).to_be_visible()
    expect(popover.get_by_text("same-email@example.test", exact=True)).to_be_visible()
    expect(popover.get_by_role("link", name="Manage usage").first).to_have_attribute(
        "href", "https://chatgpt.com/settings/usage"
    )
    previous_count = stats()["generated"]
    popover.get_by_role("button", name="Connect another account", exact=True).click()
    expect(popover.get_by_role("combobox", name="Switch ChatGPT account")).to_have_count(1)
    expect(popover.locator("select option")).to_have_count(2, timeout=15000)
    assert stats()["generated"] == previous_count
    page.keyboard.press("Escape")
    expect(page.get_by_label("AI connection settings", exact=True)).to_be_focused()
    before = (path / "project.json").read_bytes()
    for state, label in (
        ("offline", "ChatGPT temporarily unavailable"),
        ("limited", "ChatGPT usage limit reached"),
        ("not_permitted", "ChatGPT · plan access not enabled"),
        ("connected", "ChatGPT connected"),
    ):
        control(state)
        page.reload()
        expect(page.get_by_role("status").filter(has_text=label)).to_be_visible()
        for width, height in ((1280, 720), (1440, 900), (390, 844), (320, 844)):
            page.set_viewport_size({"width": width, "height": height})
            page.get_by_label("AI connection settings", exact=True).click()
            expect(page.locator(".connection-details")).to_be_visible()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=f"/tmp/sigma-a82-{state}-{width}.png")
            page.keyboard.press("Escape")
    page.get_by_label("AI connection settings", exact=True).click()
    popover.get_by_text("Use API key (advanced)", exact=True).click()
    popover.get_by_role("button", name="Use API key · billed separately", exact=True).click()
    expect(page.get_by_role("status").filter(has_text="OpenAI API · key billing")).to_be_visible()
    assert stats()["generated"] == previous_count
    popover.get_by_role("button", name="Use ChatGPT plan", exact=True).click()
    expect(page.get_by_role("status").filter(has_text="ChatGPT connected")).to_be_visible()
    control("expired")
    page.reload()
    expect(page.get_by_role("status").filter(has_text="Reconnect ChatGPT")).to_be_visible()
    assert (path / "project.json").read_bytes() == before and stats()["generated"] == previous_count
    assert not errors, errors
    print(
        "PASS header account menu/switch without inference, no billing fallback, explicit API mode, outage/limit/permission/expiry states, keyboard focus, no project mutation/JS errors, 1280/1440/390/320px"
    )
    browser.close()
