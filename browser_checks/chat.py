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
fail_next_turn = False
selected_settings = {
    "limits": {},
    "ai_model": "gpt-6.1-sol",
    "reasoning_effort": "low",
    "show_advanced_outcome_details": False,
}
supervisor_calls: list[dict] = []

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=CHROME, headless=True)
    page = browser.new_page(viewport={"width": 1360, "height": 900})
    page.on("pageerror", lambda error: errors.append(str(error)))

    def respond(route):
        global config_calls, session_calls, fail_next_turn
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
        if "/api/ai/connection" in url:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "mode": "chatgpt",
                        "status": "connected",
                        "label": "ChatGPT",
                        "guidance": "Ready.",
                        "checked_at": None,
                        "ttl_seconds": 300,
                        "accounts": [],
                    }
                ),
            )
            return
        if url.endswith("/api/user-preferences/research-settings"):
            if route.request.method == "PUT":
                selected_settings.update(route.request.post_data_json)
            route.fulfill(
                status=200, content_type="application/json", body=json.dumps(selected_settings)
            )
            return
        if url.endswith("/api/ai/models"):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "models": [
                            {
                                "id": "gpt-6-luna",
                                "label": "Luna · Economy ($)",
                                "relative_cost": "$",
                                "efforts": ["low", "medium", "high", "xhigh"],
                            },
                            {
                                "id": "gpt-6.1-sol",
                                "label": "Sol · Balanced ($$)",
                                "relative_cost": "$$",
                                "efforts": ["low", "medium", "high", "xhigh"],
                            },
                        ],
                    }
                ),
            )
            return
        if url.endswith("/api/chat/supervisor"):
            supervisor_calls.append(route.request.post_data_json)
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "score": 3.4,
                        "rubric": {
                            "alignment": 0.9,
                            "originality": 0.6,
                            "advancement": 0.7,
                            "evidence": 0.8,
                            "momentum": 0.4,
                        },
                        "assessment": "The pair is exploring constructively.",
                        "action": "continue",
                        "recipient": None,
                        "guidance": "",
                        "breakthrough_candidate": False,
                        "breakthrough_invalidated": False,
                    }
                ),
            )
            return
        if url.endswith("/api/chat/turn"):
            body = route.request.post_data_json
            turns.append(body)
            if fail_next_turn:
                fail_next_turn = False
                route.fulfill(
                    status=200,
                    content_type="text/event-stream",
                    body='data: {"type":"started"}\n\ndata: {"type":"error","error":"Provider unavailable"}\n\n',
                )
                return
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
    page.goto(ORIGIN + "/", wait_until="networkidle")
    expect(page.get_by_role("button", name="Brainstorm", exact=True)).to_have_count(0)
    # Direct URL must work without --brainstorm, and unlock the Home pill
    # when returning via in-app navigation. This also covers a hard URL load.
    direct = browser.new_page()
    direct.route("**/api/**", respond)
    direct.goto(ORIGIN + "/brainstorm", wait_until="networkidle")
    expect(direct).to_have_url(ORIGIN + "/brainstorm")
    expect(direct.locator(".brainstorm-header-copy h1")).to_have_text("Brainstorm")
    direct.locator(".project-art-header .project-header-art").click()
    expect(direct).to_have_url(ORIGIN + "/")
    expect(direct.get_by_role("button", name="Brainstorm", exact=True)).to_be_visible()
    direct.get_by_role("button", name="Brainstorm", exact=True).click()
    expect(direct.locator(".brainstorm-header-copy h1")).to_have_text("Brainstorm")
    direct.close()

    # The CLI flag remains a convenient way to start with the Home pill.
    page.goto(ORIGIN + "/?brainstorm=1", wait_until="networkidle")
    expect(page).to_have_url(ORIGIN + "/")
    page.get_by_role("button", name="Brainstorm", exact=True).click()
    expect(page).to_have_url(ORIGIN + "/brainstorm")
    expect(page.locator(".brainstorm-header-copy h1")).to_have_text("Brainstorm")
    expect(page.locator(".project-art-header .project-header-art")).to_be_visible()
    assert page.locator(".chat-home-link").count() == 0
    page.locator(".project-art-header .project-header-art").click()
    expect(page).to_have_url(ORIGIN + "/")
    expect(page.get_by_role("button", name="Brainstorm", exact=True)).to_be_visible()
    page.get_by_role("button", name="Brainstorm", exact=True).click()
    expect(page).to_have_url(ORIGIN + "/brainstorm")
    # Desktop header: three distinct text lines, artwork left, Home-aligned
    # account/model pills right. Verify at the reported wide screenshot size.
    page.set_viewport_size({"width": 2048, "height": 900})
    header = page.locator(".chat-site-header")
    artwork_box = header.locator(".project-header-art").bounding_box()
    heading_box = header.locator(".brainstorm-header-copy").bounding_box()
    eyebrow_box = header.locator(".chat-eyebrow").bounding_box()
    title_box = header.locator(".brainstorm-header-copy h1").bounding_box()
    description_box = header.locator(".brainstorm-header-copy .chat-description").bounding_box()
    google_box = header.locator(".project-google-signin").bounding_box()
    chatgpt_box = header.locator(".api-connection > summary").bounding_box()
    model_box = header.locator(".brainstorm-header-model-column .global-model-pill").bounding_box()
    header_box = header.bounding_box()
    assert all(
        (
            artwork_box,
            heading_box,
            eyebrow_box,
            title_box,
            description_box,
            google_box,
            chatgpt_box,
            model_box,
            header_box,
        )
    )
    # Rendering, not just column positions: the oversized artwork made the
    # entire header 365px tall and cropped the wordmark in the user smoke test.
    assert artwork_box["width"] <= 340, artwork_box
    assert artwork_box["height"] <= 245, artwork_box
    assert 160 <= header_box["height"] <= 170, header_box
    assert artwork_box["x"] + artwork_box["width"] <= heading_box["x"] + 2
    assert description_box["x"] + description_box["width"] <= google_box["x"] - 4
    assert eyebrow_box["y"] + eyebrow_box["height"] <= title_box["y"] + 3
    assert title_box["y"] + title_box["height"] <= description_box["y"] + 3
    assert description_box["height"] < 28, "Description should occupy exactly one line"
    assert model_box["x"] + model_box["width"] <= google_box["x"] - 4
    assert abs(google_box["y"] - model_box["y"]) < 4
    assert chatgpt_box["y"] >= google_box["y"] + google_box["height"] + 8
    assert 10 <= 2048 - max(
        google_box["x"] + google_box["width"],
        chatgpt_box["x"] + chatgpt_box["width"],
    ) <= 28
    assert 10 <= google_box["y"] - header_box["y"] <= 28
    page.set_viewport_size({"width": 1360, "height": 900})
    human = page.get_by_label("Human", exact=True)
    first = page.get_by_role("region", name="AI #1 latest reply")
    second = page.get_by_role("region", name="AI #2 latest reply")
    expect(human).to_be_visible()
    expect(first).to_be_visible()
    expect(second).to_be_visible()
    expect(page.locator(".brainstorm-header-model-column .global-model-pill")).to_be_visible()
    assert page.locator(".chat-site-header .brainstorm-header-model-column button").count() == 1
    assert page.locator(".chat-site-header .project-google-signin").count() >= 1
    assert first.locator("textarea").count() == 0
    assert second.locator("textarea").count() == 0
    expect(page.get_by_text("Edit reply text", exact=True)).to_have_count(0)
    toolbar = page.get_by_role("region", name="Brainstorm exchange controls")
    expect(toolbar).to_be_visible()
    metadata = page.locator(".chat-privacy-note")
    expect(metadata).to_contain_text("Transcript file:")
    assert "Messages are appended" not in metadata.inner_text()
    title_bounds = page.locator(".chat-site-header .brainstorm-header-copy").bounding_box()
    metadata_bounds = metadata.bounding_box()
    supervisor_panel = page.get_by_role("region", name="Brainstorm supervisor")
    # A global input width:100% rule previously stretched this checkbox
    # nearly the entire panel and pushed the label to its far edge.
    supervisor_checkbox = page.get_by_label("Enable Supervisor")
    checkbox_bounds = supervisor_checkbox.bounding_box()
    checkbox_label_bounds = supervisor_panel.locator("label").bounding_box()
    panel_bounds = supervisor_panel.bounding_box()
    assert checkbox_bounds and checkbox_label_bounds and panel_bounds
    assert 15 <= checkbox_bounds["width"] <= 20, checkbox_bounds
    assert 15 <= checkbox_bounds["height"] <= 20, checkbox_bounds
    assert checkbox_label_bounds["width"] < 240, checkbox_label_bounds
    assert abs(checkbox_bounds["x"] - (panel_bounds["x"] + 15)) < 4
    assert checkbox_label_bounds["x"] <= panel_bounds["x"] + 20
    objective_copy = page.get_by_role("button", name="Copy Research Objective")
    human_copy = page.get_by_role("button", name="Copy Human")
    objective_label = page.locator(".chat-repeated-prompt .chat-field-heading label").bounding_box()
    human_label = page.locator(".chat-human-form .chat-field-heading label").bounding_box()
    objective_icon = objective_copy.bounding_box()
    human_icon = human_copy.bounding_box()
    assert objective_label and human_label and objective_icon and human_icon
    for label_box, icon_box in ((objective_label, objective_icon), (human_label, human_icon)):
        gap = icon_box["x"] - (label_box["x"] + label_box["width"])
        assert 0 <= gap <= 12, (label_box, icon_box)
        assert abs(
            (label_box["y"] + label_box["height"] / 2)
            - (icon_box["y"] + icon_box["height"] / 2)
        ) <= 9, (label_box, icon_box)
    expect(objective_copy).to_be_disabled()
    expect(human_copy).to_be_disabled()
    repeated = page.get_by_label("Research Objective:", exact=True)
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
    )
    assert repeated_bounds["width"] >= page_bounds["width"] - 4
    assert human_bounds["width"] >= page_bounds["width"] - 4
    assert abs(first_bounds["y"] - second_bounds["y"]) < 2
    assert first_bounds["x"] < second_bounds["x"]
    assert first_bounds["width"] >= page_bounds["width"] * 0.40
    assert second_bounds["width"] >= page_bounds["width"] * 0.40
    assert abs(first_bounds["x"] - page_bounds["x"]) < 3
    assert (
        abs(
            (second_bounds["x"] + second_bounds["width"])
            - (page_bounds["x"] + page_bounds["width"])
        )
        < 3
    )
    assert repeated.get_attribute("rows") == "2"
    assert human.get_attribute("rows") == "2"
    assert repeated.get_attribute("maxlength") is None
    assert human.get_attribute("maxlength") is None
    assert page.locator(".chat-field-heading small").count() == 0
    repeated.fill("R" * 8100)
    assert len(repeated.input_value()) == 8100
    human.fill("H" * 8100)
    assert len(human.input_value()) == 8100
    expect(human_copy).to_be_enabled()
    human.fill("")
    expect(human_copy).to_be_disabled()
    repeated.fill("A")
    narrow_bounds = repeated.bounding_box()
    repeated.fill("Find a new mathematical breakthrough.")
    expect(objective_copy).to_be_enabled()
    filled_bounds = repeated.bounding_box()
    assert narrow_bounds is not None and filled_bounds is not None
    assert abs(narrow_bounds["width"] - filled_bounds["width"]) < 1
    assert abs(narrow_bounds["x"] - filled_bounds["x"]) < 1
    transcript_filename = page.locator(".chat-privacy-note code")
    expect(transcript_filename).to_contain_text("/chat-transcripts/20261114_120004.md")
    expect(transcript_filename).to_contain_text(".md")
    expect(page.get_by_role("button", name="Send", exact=True)).to_be_visible()
    model_pill = page.locator(".brainstorm-header-model-column .global-model-pill")
    expect(model_pill).to_contain_text("GPT-6.1-Sol")
    expect(model_pill).to_contain_text("Thinking · Low")
    model_pill.click(position={"x": 12, "y": 8})
    expect(model_pill).to_contain_text("GPT-6-Luna")
    bounds = model_pill.bounding_box()
    assert bounds is not None
    model_pill.click(position={"x": 12, "y": int(bounds["height"]) - 8})
    expect(model_pill).to_contain_text("Thinking · Medium")
    connection = page.locator(".chat-site-header .header-controls .api-connection")
    connection_bounds = connection.locator("summary").bounding_box()
    model_bounds = model_pill.bounding_box()
    assert connection_bounds and model_bounds
    assert model_bounds["x"] + model_bounds["width"] < connection_bounds["x"] + 5
    title_right = title_bounds["x"] + title_bounds["width"]
    pill_left = min(connection_bounds["x"], model_bounds["x"])
    assert title_right <= pill_left + 5, (title_bounds, connection_bounds, model_bounds)

    human.fill("Start the two-agent exchange.")
    expect(page.get_by_role("button", name="Send", exact=True)).to_be_enabled()
    page.get_by_role("button", name="Send", exact=True).click()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and not turns:
        page.wait_for_timeout(50)
    assert turns, "The first AI turn was not requested."
    assert turns[0]["research_objective"] == "Find a new mathematical breakthrough."
    assert turns[0]["model"] == "gpt-6-luna"
    assert turns[0]["reasoning_effort"] == "medium"
    expect(first.locator(".chat-markdown strong")).to_have_text("formatted")
    expect(first.locator(".katex")).to_be_visible()
    expect(second.locator(".chat-markdown strong")).to_have_text("formatted")

    before_repeated_edit = len(turns)
    page.get_by_label("Enable Supervisor").check()
    human_messages_before = sum(message["speaker"] == "human" for message in transcript_messages)
    repeated.fill("New objective applies without a Human message.")
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and not any(
        turn["research_objective"] == "New objective applies without a Human message."
        for turn in turns[before_repeated_edit:]
    ):
        page.wait_for_timeout(100)
    assert any(
        turn["research_objective"] == "New objective applies without a Human message."
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
    assert turns[0]["research_objective"] == "Find a new mathematical breakthrough."
    assert all(
        turn["research_objective"] == "New objective applies without a Human message."
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
    assert session_calls == 4
    assert supervisor_calls, "Supervisor should assess at least one completed AI pair"
    assert any(item["speaker"] == "supervisor" for item in transcript_messages)
    assert any(item["speaker"] == "objective" for item in transcript_messages)

    # A failed AI turn must expose Retry and resume the same speaker, without
    # appending a second Human prompt or restarting at AI #1 arbitrarily.
    fail_next_turn = True
    human.fill("Please continue even if the provider fails.")
    page.get_by_role("button", name="Send", exact=True).click()
    retry = page.get_by_role("button", name="Retry AI #1", exact=True)
    expect(retry).to_be_visible(timeout=5000)
    expect(page.get_by_role("alert")).to_contain_text("Provider unavailable")
    failed_index = len(turns) - 1
    failed_request = turns[failed_index]
    assert failed_request["speaker"] == "ai_1"
    human_writes = sum(item["speaker"] == "human" for item in transcript_messages)
    retry.click()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and len(turns) <= failed_index + 1:
        page.wait_for_timeout(50)
    assert len(turns) > failed_index + 1, "Retry did not dispatch the failed turn"
    assert turns[failed_index + 1]["speaker"] == "ai_1"
    assert turns[failed_index + 1]["messages"] == failed_request["messages"]
    expect(retry).to_have_count(0)
    assert sum(item["speaker"] == "human" for item in transcript_messages) == human_writes
    page.get_by_role("button", name="Stop exchange", exact=True).click()

    page.get_by_role("button", name="Clear", exact=True).click()
    expect(transcript_filename).to_contain_text("/chat-transcripts/20261114_120005.md")
    assert session_calls == 5
    # A new normal page load must not inherit the earlier local opt-in.
    page.goto(ORIGIN + "/", wait_until="networkidle")
    expect(page.get_by_role("button", name="Brainstorm", exact=True)).to_have_count(0)
    assert not errors, errors
    assert config_calls >= 1
    browser.close()

print(
    "PASS Chrome chat model/thinking controls, Markdown/math, transcript append, two-agent alternation, intervention, and stop"
)
