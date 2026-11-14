"""Real-Chrome chat UI check with deterministic connection and turn responses."""

import json
import os

from playwright.sync_api import expect, sync_playwright

ORIGIN = os.environ.get("SIGMA_CHAT_UI_ORIGIN", "http://127.0.0.1:5173").rstrip("/")
CHROME = os.environ.get(
    "SIGMA_BROWSER_EXECUTABLE",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)
turns: list[dict] = []
errors: list[str] = []
config_calls = 0

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=CHROME, headless=True)
    page = browser.new_page(viewport={"width": 1360, "height": 900})
    page.on("pageerror", lambda error: errors.append(str(error)))

    def respond(route):
        global config_calls
        url = route.request.url
        if url.endswith("/api/chat/config"):
            config_calls += 1
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "available": True,
                        "mode": "chatgpt",
                        "status": "connected",
                        "message": "Ready.",
                        "binding": "fixture-account",
                        "model": "gpt-6.1-sol",
                        "reasoning_effort": "low",
                        "max_messages": 80,
                        "max_message_characters": 8000,
                    }
                ),
            )
            return
        if url.endswith("/api/chat/turn"):
            body = route.request.post_data_json
            turns.append(body)
            route.fulfill(
                status=200,
                content_type="text/event-stream",
                body=(
                    'data: {"type":"started"}\n\n'
                    + "data: "
                    + json.dumps(
                        {"type": "complete", "text": f"{body['speaker']} reply {len(turns)}"}
                    )
                    + "\n\n"
                ),
            )
            return
        if "/api/" in url:
            route.fulfill(status=200, content_type="application/json", body="{}")
            return
        route.continue_()

    page.route("**/api/**", respond)
    page.goto(ORIGIN + "/chat", wait_until="networkidle")
    human = page.get_by_label("Human", exact=True)
    first = page.get_by_label("AI #1 latest reply; editable")
    second = page.get_by_label("AI #2 latest reply; editable")
    expect(human).to_be_visible()
    expect(first).to_be_visible()
    expect(second).to_be_visible()
    expect(page.get_by_role("button", name="Send", exact=True)).to_be_visible()

    human.fill("Start the two-agent exchange.")
    expect(page.get_by_role("button", name="Send", exact=True)).to_be_enabled()
    page.get_by_role("button", name="Send", exact=True).click()
    expect(first).to_have_value("ai_1 reply 1")
    expect(second).to_have_value("ai_2 reply 2")

    human.fill("Human intervention: focus on the counterexample.")
    page.get_by_role("button", name="Send", exact=True).click()
    expect(first).to_have_value("ai_1 reply 3")
    assert turns[:3] and [turn["speaker"] for turn in turns[:3]] == ["ai_1", "ai_2", "ai_1"]
    assert any(
        item["speaker"] == "human"
        and item["text"] == "Human intervention: focus on the counterexample."
        for item in turns[2]["messages"]
    )
    page.get_by_role("button", name="Stop exchange", exact=True).click()
    expect(page.get_by_role("button", name="Clear conversation", exact=True)).to_be_visible()
    assert page.get_by_role("list", name="Conversation history").locator("li").count() >= 4
    assert not errors, errors
    assert config_calls >= 1
    browser.close()

print("PASS Chrome chat boxes, AI #1/AI #2 alternation, human intervention, and stop control")
