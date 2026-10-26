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
        if route.request.url.endswith("/api/cloud-auth/status"):
            route.fulfill(
                status=200,
                content_type="application/json",
                body='{"target":"local","enabled":false,"ready":true,"authenticated":false,"user":null,"admin_contact_email":null,"local_setup_missing":[]}',
            )
            return
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
        page.locator(".api-connection > summary").click()
        return page.get_by_role("dialog", name="AI connection settings")

    def no_credential_text():
        for alert in page.get_by_role("alert").all():
            if SENSITIVE_SHAPES.search(alert.inner_text()):
                leaks.append("user-facing error")
        assert not leaks, f"Credential-shaped text appeared in {sorted(set(leaks))}"

    panel = connection_panel()
    connect = panel.get_by_role("button", name="Continue with ChatGPT", exact=True)

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
    expect(panel).to_contain_text("plan allowance or credits")
    expect(panel.get_by_text("same-email@example.test", exact=True)).to_be_visible()
    no_credential_text()

    # Add a distinct ChatGPT identity in the same browser profile. The new
    # identity becomes active, survives reload, and can be explicitly switched
    # back to the retained first account without exposing credentials.
    identity_change = context.request.post(
        f"{FIXTURE_ORIGIN}/__fixture__/state",
        data={
            "state": "connected",
            "subject": "fixture-subject-two",
            "email": "second-account@example.test",
        },
    )
    assert identity_change.ok
    panel.get_by_role("button", name="Connect another account", exact=True).click()
    expect(status.filter(has_text="ChatGPT connected")).to_be_visible(timeout=20000)
    expect(panel.get_by_text("second-account@example.test", exact=True)).to_be_visible()
    second_state = page.evaluate("async () => (await (await fetch('/api/ai/connection')).json())")
    assert len(second_state["accounts"]) == 2, second_state
    second_id = second_state["active_account"]
    first_id = next(item["id"] for item in second_state["accounts"] if item["id"] != second_id)
    page.reload()
    expect(status.filter(has_text="ChatGPT connected")).to_be_visible(timeout=15000)
    connection_panel()
    expect(
        page.get_by_role("dialog", name="AI connection settings").get_by_text(
            "second-account@example.test", exact=True
        )
    ).to_be_visible()
    switched = page.evaluate(
        "async (accountId) => { const response = await fetch('/api/ai/mode', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({mode:'chatgpt', account_id:accountId}) }); return {ok: response.ok, body: await response.json()}; }",
        first_id,
    )
    assert switched["ok"] and switched["body"]["active_account"] == first_id, switched
    page.reload()
    expect(status.filter(has_text="ChatGPT connected")).to_be_visible(timeout=15000)
    connection_panel()
    expect(
        page.get_by_role("dialog", name="AI connection settings").get_by_text(
            "same-email@example.test", exact=True
        )
    ).to_be_visible()
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
    "PASS real Chrome isolated ChatGPT sign-in, decline, distinct-account connect/reload/switch, outage/limit/permission/expiry recovery, sanitized UI/console, and zero inference calls; cancellation is covered by the API regression"
)
