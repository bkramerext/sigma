"""Hosted Brainstorm is hidden on Home until visited, but remains member-gated."""

import json
import os
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

ORIGIN = os.environ.get("SIGMA_CHAT_UI_ORIGIN", "http://127.0.0.1:5173").rstrip("/")
CHROMIUM = os.environ.get("SIGMA_BROWSER_EXECUTABLE")
account = {"role": None}
request_turns = []

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=CHROMIUM, headless=True)
    page = browser.new_page()

    def hosted_api(route):
        url = route.request.url
        if url.endswith("/api/cloud-auth/status"):
            role = account["role"]
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "enabled": True,
                        "ready": True,
                        "authenticated": role is not None,
                        "user": {"email": "member@example.org", "role": role} if role else None,
                        "target": "hosted",
                        "admin_contact_email": None,
                    }
                ),
            )
        elif url.endswith("/api/chat/config"):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "available": True,
                        "mode": "chatgpt",
                        "status": "connected",
                        "message": "Ready.",
                        "binding": "fixture-sponsored",
                        "model": "gpt-6.1-sol",
                        "models": [
                            {
                                "id": "gpt-6.1-sol",
                                "label": "Sol",
                                "relative_cost": "$$",
                                "efforts": ["low"],
                            }
                        ],
                        "reasoning_effort": "low",
                        "max_messages": 80,
                    }
                ),
            )
        elif url.endswith("/api/chat/session"):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "conversation_id": str(uuid4()),
                        "transcript_path": "/fixture/transcript.md",
                    }
                ),
            )
        elif url.endswith("/api/chat/message"):
            route.fulfill(status=204, body="")
        elif url.endswith("/api/chat/turn"):
            request_turns.append(route.request.post_data_json)
            route.fulfill(
                status=200,
                content_type="text/event-stream",
                body=(
                    'data: {"type":"started"}\n\n'
                    'data: {"type":"complete","text":"Hosted fixture response."}\n\n'
                ),
            )
        else:
            route.fulfill(status=404, content_type="application/json", body='{"error":"fixture"}')

    page.route("**/api/**", hosted_api)
    page.goto(ORIGIN + "/", wait_until="domcontentloaded")
    expect(page.get_by_role("button", name="Brainstorm", exact=True)).to_have_count(0)

    # A direct URL never bypasses authentication or guest authorization.
    page.goto(ORIGIN + "/brainstorm", wait_until="domcontentloaded")
    expect(page.get_by_role("status")).to_have_text(
        "Brainstorm requires a signed-in SIGMA member account."
    )
    expect(page.locator(".chat-page")).to_have_count(0)
    page.goto(ORIGIN + "/", wait_until="domcontentloaded")
    expect(page.get_by_role("button", name="Brainstorm", exact=True)).to_have_count(0)

    account["role"] = "member"
    page.goto(ORIGIN + "/", wait_until="domcontentloaded")
    expect(page.get_by_role("button", name="Brainstorm", exact=True)).to_have_count(0)
    page.goto(ORIGIN + "/brainstorm", wait_until="networkidle")
    expect(page.locator(".chat-page-header h1")).to_have_text("Brainstorm")
    page.get_by_label("Human", exact=True).fill("Try a fresh approach.")
    page.get_by_role("button", name="Send", exact=True).click()
    expect(page.get_by_role("region", name="AI #1 latest reply")).to_contain_text(
        "Hosted fixture response."
    )
    assert request_turns and request_turns[0]["speaker"] == "ai_1"
    page.locator(".project-art-header .project-header-art").click()
    expect(page).to_have_url(ORIGIN + "/")
    expect(page.get_by_role("button", name="Brainstorm", exact=True)).to_be_visible()
    page.reload(wait_until="domcontentloaded")
    expect(page.get_by_role("button", name="Brainstorm", exact=True)).to_be_visible()
    page.get_by_role("button", name="Brainstorm", exact=True).click()
    expect(page.locator(".chat-page-header h1")).to_have_text("Brainstorm")

    # Unlock is tab/account scoped, not globally advertised to all users.
    second = browser.new_page()
    second.route("**/api/**", hosted_api)
    second.goto(ORIGIN + "/", wait_until="domcontentloaded")
    expect(second.get_by_role("button", name="Brainstorm", exact=True)).to_have_count(0)
    second.goto(ORIGIN + "/chat", wait_until="networkidle")
    expect(second.locator(".chat-page-header h1")).to_have_text("Brainstorm")
    second.goto(ORIGIN + "/", wait_until="domcontentloaded")
    expect(second.get_by_role("button", name="Brainstorm", exact=True)).to_be_visible()

    account["role"] = "guest"
    page.goto(ORIGIN + "/", wait_until="domcontentloaded")
    expect(page.get_by_role("button", name="Brainstorm", exact=True)).to_have_count(0)
    page.goto(ORIGIN + "/brainstorm", wait_until="domcontentloaded")
    expect(page.locator(".chat-page")).to_have_count(0)
    expect(page.get_by_role("status")).to_have_text(
        "Brainstorm requires a signed-in SIGMA member account."
    )

    browser.close()

print("PASS hosted Brainstorm member route, working mocked turn, tab unlock, guest fence")
