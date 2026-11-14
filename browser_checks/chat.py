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
    expect(page.locator(".project-art-header .project-header-art")).to_be_visible()
    assert page.locator(".chat-home-link").count() == 0
    page.locator(".project-art-header .project-header-art").click()
    expect(page).to_have_url(ORIGIN + "/")
    page.goto(ORIGIN + "/brainstorm", wait_until="networkidle")
    human = page.get_by_label("Human", exact=True)
    first = page.get_by_role("region", name="AI #1 latest reply")
    second = page.get_by_role("region", name="AI #2 latest reply")
    expect(human).to_be_visible()
    expect(first).to_be_visible()
    expect(second).to_be_visible()
    expect(
        page.locator(
            ".chat-site-header .header-controls .chat-header-center-slot .chat-header-model-controls"
        )
    ).to_be_visible()
    assert page.locator(".chat-page-header .chat-model-controls").count() == 0
    assert page.locator(".chat-site-header .chat-header-model-controls button").count() == 1
    assert first.locator("textarea").count() == 0
    assert second.locator("textarea").count() == 0
    expect(page.get_by_text("Edit reply text", exact=True)).to_have_count(0)
    toolbar = page.get_by_role("region", name="Brainstorm exchange controls")
    expect(toolbar).to_be_visible()
    metadata = page.locator(".chat-privacy-note")
    expect(metadata).to_contain_text("Transcript file:")
    assert "Messages are appended" not in metadata.inner_text()
    title_bounds = page.locator(".chat-page-header").bounding_box()
    metadata_bounds = metadata.bounding_box()
    repeated = page.get_by_label("Repeated:", exact=True)
    repeated_bounds = repeated.bounding_box()
    human_bounds = human.bounding_box()
    toolbar_bounds = toolbar.bounding_box()
    first_bounds = first.bounding_box()
    second_bounds = second.bounding_box()
    page_bounds = page.locator(".chat-page").bounding_box()
    assert all(
        bounds is not None
        for bounds in (
            title_bounds,
            metadata_bounds,
            repeated_bounds,
            human_bounds,
            toolbar_bounds,
            first_bounds,
            second_bounds,
            page_bounds,
        )
    )
    assert (
        title_bounds["y"]
        < metadata_bounds["y"]
        < repeated_bounds["y"]
        < human_bounds["y"]
        < toolbar_bounds["y"]
        < first_bounds["y"]
        < second_bounds["y"]
    )
    assert repeated_bounds["width"] >= page_bounds["width"] - 4
    assert human_bounds["width"] >= page_bounds["width"] - 4
    assert first_bounds["width"] >= page_bounds["width"] - 4
    assert second_bounds["width"] >= page_bounds["width"] - 4
    assert repeated.get_attribute("rows") == "2"
    assert human.get_attribute("rows") == "2"
    repeated.fill("A")
    narrow_bounds = repeated.bounding_box()
    repeated.fill("Always challenge the assumptions.")
    filled_bounds = repeated.bounding_box()
    assert narrow_bounds is not None and filled_bounds is not None
    assert abs(narrow_bounds["width"] - filled_bounds["width"]) < 1
    assert abs(narrow_bounds["x"] - filled_bounds["x"]) < 1
    transcript_filename = page.locator(".chat-privacy-note code")
    expect(transcript_filename).to_contain_text("/chat-transcripts/20261114_120001.md")
    expect(transcript_filename).to_contain_text(".md")
    expect(page.get_by_role("button", name="Send", exact=True)).to_be_visible()
    model_pill = page.locator(".chat-header-model-controls .global-model-pill")
    expect(model_pill).to_contain_text("GPT-6.1-Sol")
    expect(model_pill).to_contain_text("Thinking · Low")
    model_pill.click(position={"x": 12, "y": 8})
    expect(model_pill).to_contain_text("GPT-6-Luna")
    bounds = model_pill.bounding_box()
    assert bounds is not None
    model_pill.click(position={"x": 12, "y": int(bounds["height"]) - 8})
    expect(model_pill).to_contain_text("Thinking · Medium")
    connection = page.locator(".chat-site-header .header-controls .api-connection")
    connection_bounds = connection.bounding_box()
    model_bounds = model_pill.bounding_box()
    assert connection_bounds and model_bounds
    assert connection_bounds["x"] + connection_bounds["width"] < model_bounds["x"]
    assert (
        abs(
            (connection_bounds["y"] + connection_bounds["height"] / 2)
            - (model_bounds["y"] + model_bounds["height"] / 2)
        )
        < 8
    )

    human.fill("Start the two-agent exchange.")
    expect(page.get_by_role("button", name="Send", exact=True)).to_be_enabled()
    page.get_by_role("button", name="Send", exact=True).click()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and not turns:
        page.wait_for_timeout(50)
    assert turns, "The first AI turn was not requested."
    assert turns[0]["repeated_text"] == "Always challenge the assumptions."
    assert turns[0]["model"] == "gpt-6-luna"
    assert turns[0]["reasoning_effort"] == "medium"
    expect(first.locator(".chat-markdown strong")).to_have_text("formatted")
    expect(first.locator(".katex")).to_be_visible()
    expect(second.locator(".chat-markdown strong")).to_have_text("formatted")

    before_repeated_edit = len(turns)
    human_messages_before = sum(message["speaker"] == "human" for message in transcript_messages)
    repeated.fill("New instruction applies without a Human message.")
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and not any(
        turn["repeated_text"] == "New instruction applies without a Human message."
        for turn in turns[before_repeated_edit:]
    ):
        page.wait_for_timeout(100)
    assert any(
        turn["repeated_text"] == "New instruction applies without a Human message."
        for turn in turns[before_repeated_edit:]
    )
    assert (
        sum(message["speaker"] == "human" for message in transcript_messages)
        == human_messages_before
    )
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
    assert turns[0]["repeated_text"] == "Always challenge the assumptions."
    assert all(
        turn["repeated_text"] == "New instruction applies without a Human message."
        for turn in turns[before_intervention:]
    )
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
    expect(page.get_by_role("button", name="Clear", exact=True)).to_be_enabled()
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
    page.get_by_role("button", name="Clear", exact=True).click()
    expect(transcript_filename).to_contain_text("/chat-transcripts/20261114_120002.md")
    assert session_calls == 2
    assert not errors, errors
    assert config_calls >= 1
    browser.close()

print(
    "PASS Chrome chat model/thinking controls, Markdown/math, transcript append, two-agent alternation, intervention, and stop"
)
