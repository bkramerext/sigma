"""Real-Chrome chat UI check with deterministic connection and turn responses."""

import json
import os
import time
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

ORIGIN = os.environ.get("SIGMA_CHAT_UI_ORIGIN", "http://127.0.0.1:5173").rstrip("/")
CHROME = os.environ.get(
    "SIGMA_BROWSER_EXECUTABLE",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)
turns: list[dict] = []
errors: list[str] = []
config_calls = 0
session_calls = 0
transcript_messages: list[dict] = []

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=CHROME, headless=True)
    page = browser.new_page(viewport={"width": 1360, "height": 900})
    page.on("pageerror", lambda error: errors.append(str(error)))

    def respond(route):
        global config_calls, session_calls
        url = route.request.url
        if url.endswith("/api/chat/session"):
            session_calls += 1
            conversation_id = str(uuid4())
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "conversation_id": conversation_id,
                        "transcript_name": f"20261114_12000{session_calls}.md",
                        "transcript_path": f"/tmp/sigma-state/chat-transcripts/20261114_12000{session_calls}.md",
                    }
                ),
            )
            return
        if url.endswith("/api/chat/message"):
            transcript_messages.append(route.request.post_data_json)
            route.fulfill(status=204, body="")
            return
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
                        "models": [
                            {
                                "id": "gpt-6.1-sol",
                                "label": "Sol · Balanced ($$)",
                                "relative_cost": "$$",
                                "efforts": ["low", "medium", "high", "xhigh"],
                            },
                            {
                                "id": "gpt-6-luna",
                                "label": "Luna · Economy ($)",
                                "relative_cost": "$",
                                "efforts": ["low", "medium", "high", "xhigh"],
                            },
                        ],
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
    page.goto(ORIGIN + "/brainstorm", wait_until="networkidle")
    expect(page.locator(".chat-page-header h1")).to_have_text("Brainstorm")
    human = page.get_by_label("Human", exact=True)
    first = page.get_by_role("region", name="AI #1 latest reply")
    second = page.get_by_role("region", name="AI #2 latest reply")
    expect(human).to_be_visible()
    expect(first).to_be_visible()
    expect(second).to_be_visible()
    expect(
        page.locator(".chat-site-header .chat-header-center-slot .chat-header-model-controls")
    ).to_be_visible()
    assert page.locator(".chat-page-header .chat-model-controls").count() == 0
    assert (
        page.locator(".chat-site-header .header-controls .chat-header-model-controls").count() == 0
    )
    assert first.locator("textarea").count() == 0
    assert second.locator("textarea").count() == 0
    expect(page.get_by_text("Edit reply text", exact=True)).to_have_count(0)
    transcript_filename = page.locator(".chat-privacy-note code")
    expect(transcript_filename).to_contain_text("/chat-transcripts/20261114_120001.md")
    expect(transcript_filename).to_contain_text(".md")
    expect(page.get_by_role("button", name="Send", exact=True)).to_be_visible()
    model_pill = page.get_by_role("button", name="Model gpt-6.1-sol")
    thinking_pill = page.get_by_role("button", name="Thinking level Low")
    model_pill.click()
    expect(page.get_by_role("button", name="Model gpt-6-luna")).to_be_visible()
    thinking_pill.click()
    expect(page.get_by_role("button", name="Thinking level Medium")).to_be_visible()

    human.fill("Start the two-agent exchange.")
    expect(page.get_by_role("button", name="Send", exact=True)).to_be_enabled()
    page.get_by_role("button", name="Send", exact=True).click()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and not turns:
        page.wait_for_timeout(50)
    assert turns, "The first AI turn was not requested."
    assert turns[0]["model"] == "gpt-6-luna"
    assert turns[0]["reasoning_effort"] == "medium"
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
    expect(page.get_by_text("Edit reply text", exact=True)).to_have_count(0)
    history = page.get_by_role("list", name="Conversation history")
    assert history.locator("li").count() >= 4
    expect(history.locator(".chat-history-ai_2 .chat-markdown strong").first).to_have_text(
        "formatted"
    )
    expect(history.locator(".chat-history-ai_2 .katex").first).to_be_visible()
    assert any(
        message["speaker"] == "human" and message["text"] == "Start the two-agent exchange."
        for message in transcript_messages
    )
    assert any(message["speaker"] == "ai_1" for message in transcript_messages)
    assert any(message["speaker"] == "ai_2" for message in transcript_messages)
    assert any(
        message["speaker"] == "human"
        and message["text"] == "Human intervention: focus on the counterexample."
        for message in transcript_messages
    )
    assert session_calls == 1
    page.get_by_role("button", name="Clear conversation", exact=True).click()
    expect(transcript_filename).to_contain_text("/chat-transcripts/20261114_120002.md")
    assert session_calls == 2
    assert not errors, errors
    assert config_calls >= 1
    browser.close()

print(
    "PASS Chrome chat model/thinking controls, Markdown/math, transcript append, two-agent alternation, intervention, and stop"
)
