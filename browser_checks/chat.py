"""Real-Chrome chat UI check with deterministic connection and turn responses."""

import json
import os
import time

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
                        {
                            "type": "complete",
                            "text": (
                                f"{body['speaker']} **formatted** reply {len(turns)}\n\n"
                                r"Value: \(8.08\times10^{53}\)."
                            ),
                        }
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
    first = page.get_by_role("region", name="AI #1 latest reply")
    second = page.get_by_role("region", name="AI #2 latest reply")
    expect(human).to_be_visible()
    expect(first).to_be_visible()
    expect(second).to_be_visible()
    expect(page.get_by_role("button", name="Send", exact=True)).to_be_visible()

    human.fill("Start the two-agent exchange.")
    expect(page.get_by_role("button", name="Send", exact=True)).to_be_enabled()
    page.get_by_role("button", name="Send", exact=True).click()
    expect(first.locator(".chat-markdown strong")).to_have_text("formatted")
    expect(first.locator(".katex")).to_be_visible()
    expect(second.locator(".chat-markdown strong")).to_have_text("formatted")

    before_intervention = len(turns)
    human.fill("Human intervention: focus on the counterexample.")
    page.get_by_role("button", name="Send", exact=True).click()
    expect(first.locator(".chat-markdown strong")).to_have_text("formatted")
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and not any(
        item["speaker"] == "human"
        and item["text"] == "Human intervention: focus on the counterexample."
        for turn in turns[before_intervention:]
        for item in turn["messages"]
    ):
        page.wait_for_timeout(100)
    assert len(turns) >= 2
    assert all(
        turn["speaker"] == ("ai_1" if index % 2 == 0 else "ai_2")
        for index, turn in enumerate(turns)
    )
    assert any(
        item["speaker"] == "human"
        and item["text"] == "Human intervention: focus on the counterexample."
        for turn in turns[before_intervention:]
        for item in turn["messages"]
    )
    page.get_by_role("button", name="Stop exchange", exact=True).click()
    expect(page.get_by_role("button", name="Clear conversation", exact=True)).to_be_visible()
    first.get_by_text("Edit reply text").click()
    editor = first.get_by_label("AI #1 reply source")
    source = editor.input_value()
    assert source.startswith("ai_1 **formatted** reply ")
    assert "Value: \\(8.08\\times10^{53}\\)." in source
    editor.fill("AI #1 **edited** reply")
    expect(first.locator(".chat-markdown strong")).to_have_text("edited")
    history = page.get_by_role("list", name="Conversation history")
    assert history.locator("li").count() >= 4
    expect(history.locator(".chat-history-ai_2 .chat-markdown strong").first).to_have_text(
        "formatted"
    )
    expect(history.locator(".chat-history-ai_2 .katex").first).to_be_visible()
    assert not errors, errors
    assert config_calls >= 1
    browser.close()

print(
    "PASS Chrome chat Markdown/math rendering, source editing, two-agent alternation, intervention, and stop"
)
