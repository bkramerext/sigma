"""Real Chrome ChatGPT connection and failure-state check against local fixtures."""

import os
import re

from playwright.sync_api import expect, sync_playwright

UI_ORIGIN = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173").rstrip("/")
FIXTURE_ORIGIN = os.environ.get("SIGMA_BROWSER_FIXTURE_URL", "http://127.0.0.1:8001").rstrip("/")
FORWARD_ORIGIN = os.environ.get("SIGMA_BROWSER_FORWARD_ORIGIN")
SENSITIVE_SHAPES = re.compile(
    r"(?i)bearer\s+\S+|fixture-(?:access|refresh)-[A-Za-z0-9_-]+|"
    r"explicit-api-key-fixture"
)


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    context = browser.new_context(viewport={"width": 1280, "height": 720})

    def scan_text(value: str) -> None:
        if SENSITIVE_SHAPES.search(value):
            leaks.append("console")

    leaks: list[str] = []

    def api(route):
        headers = None
        if FORWARD_ORIGIN:
            headers = dict(route.request.headers)
            headers["origin"] = FORWARD_ORIGIN
            headers.pop("host", None)
        response = route.fetch(
            url=route.request.url.replace(UI_ORIGIN, FIXTURE_ORIGIN),
            headers=headers,
            max_redirects=0,
        )
        if "/api/ai/auth/open/" in route.request.url and response.status == 307:
            if authorization["hold"]:
                authorization["held"].append(route)
                return
            trusted = response.headers["location"]
            assert trusted.startswith("https://auth.openai.com/api/accounts/authorize?")
            result = context.request.post(
                f"{FIXTURE_ORIGIN}/__fixture__/authorize",
                data={"url": trusted, "declined": authorization["declined"]},
            )
            assert result.ok
            route.fulfill(status=302, headers={"Location": result.json()["callback"]}, body="")
        else:
            route.fulfill(response=response)

    authorization = {"declined": False, "hold": False, "held": []}
    context.on("page", lambda page: page.on("console", lambda msg: scan_text(msg.text)))
    context.route(f"{UI_ORIGIN}/api/**", api)
    context.route("https://auth.openai.com/**", lambda route: route.abort())

    page = context.new_page()
    page.set_default_timeout(10000)
    page.goto(UI_ORIGIN + "/")
    status = page.get_by_role("status")
    expect(status.filter(has_text="Connect AI")).to_be_visible()
    assert context.request.get(f"{FIXTURE_ORIGIN}/__fixture__/stats").json()["generated"] == 0

    def connection_panel():
        page.get_by_label("AI connection settings", exact=True).click()
        return page.get_by_role("dialog", name="AI connection settings")

    def no_credential_text():
        for alert in page.get_by_role("alert").all():
            if SENSITIVE_SHAPES.search(alert.inner_text()):
                leaks.append("user-facing error")
        assert not leaks, f"Credential-shaped text appeared in {sorted(set(leaks))}"

    panel = connection_panel()
    connect = panel.get_by_role("button", name="Continue with ChatGPT", exact=True)

    # Cancel an in-progress sign-in; no model inference may occur.
    authorization["hold"] = True
    connect.click()
    expect(panel.get_by_role("button", name="Cancel sign-in", exact=True)).to_be_visible()
    panel.get_by_role("button", name="Cancel sign-in", exact=True).click()
    expect(panel.get_by_role("button", name="Continue with ChatGPT", exact=True)).to_be_enabled()
    for pending in authorization["held"]:
        pending.abort()
    authorization["held"].clear()
    authorization["hold"] = False
    no_credential_text()

    # Declined authorization is explained safely and remains retryable.
    authorization["declined"] = True
    panel.get_by_role("button", name="Continue with ChatGPT", exact=True).click()
    expect(panel.get_by_role("alert").filter(has_text="declined")).to_be_visible()
    no_credential_text()
    assert context.request.get(f"{FIXTURE_ORIGIN}/__fixture__/stats").json()["generated"] == 0

    # Complete OAuth, then verify healthy and recoverable connection states.
    authorization["declined"] = False
    panel.get_by_role("button", name="Continue with ChatGPT", exact=True).click()
    expect(status.filter(has_text="ChatGPT connected")).to_be_visible(timeout=20000)
    expect(panel.get_by_text("Using ChatGPT plan", exact=True)).to_be_visible()
    expect(panel.get_by_text("same-email@example.test", exact=True)).to_be_visible()
    no_credential_text()

    for fixture_state, expected in (
        ("offline", "ChatGPT temporarily unavailable"),
        ("limited", "ChatGPT usage limit reached"),
        ("not_permitted", "ChatGPT · plan access not enabled"),
        ("connected", "ChatGPT connected"),
        ("expired", "Reconnect ChatGPT"),
    ):
        assert context.request.post(
            f"{FIXTURE_ORIGIN}/__fixture__/state", data={"state": fixture_state}
        ).ok
        page.reload()
        expect(status.filter(has_text=expected)).to_be_visible(timeout=15000)
        no_credential_text()

    assert context.request.get(f"{FIXTURE_ORIGIN}/__fixture__/stats").json()["generated"] == 0
    browser.close()

assert not leaks, "Credential-shaped text appeared in browser output"
print(
    "PASS real Chrome isolated ChatGPT sign-in, cancel/decline, connected state, outage/limit/permission/expiry recovery, sanitized UI/console, and zero inference calls"
)
