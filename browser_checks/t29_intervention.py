"""Real Chrome check for bounded guidance during a running research session."""

import os
from urllib.parse import quote

from playwright.sync_api import expect, sync_playwright

browser_base_url = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173").rstrip("/")
fixture_base_url = os.environ.get("SIGMA_BROWSER_FIXTURE_URL", "http://127.0.0.1:8002").rstrip("/")

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
        args=["--disable-web-security"],
    )
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def forward(route):
        response = route.fetch(url=route.request.url.replace(browser_base_url, fixture_base_url))
        route.fulfill(response=response)

    page.route("**/api/**", forward)
    page.goto(browser_base_url)
    project = page.evaluate(
        """async () => {
          const response = await fetch('/api/projects/create', {
            method: 'POST', headers: {'Content-Type':'application/json'},
            body: JSON.stringify({title:'T29 Guidance Browser Verification ' + Date.now(),
              problem:'Verify bounded user guidance in a deterministic browser fixture.',
              investigation_type:'default', difficulty:'easy'})
          });
          if (!response.ok) throw new Error(await response.text());
          return response.json();
        }"""
    )
    path = project["path"]
    created = page.evaluate(
        """async path => {
          const response = await fetch('/api/projects/strategies', {
            method: 'POST', headers: {'Content-Type':'application/json'},
            body: JSON.stringify({path, title:'Pause and stop fixture strategy',
              approach:'Check the proposed recurrence and its boundary values.'})
          });
          if (!response.ok) throw new Error(await response.text());
          return response.json();
        }""",
        path,
    )
    strategy = created["project"]["strategies"][0]
    page.goto(f"{browser_base_url}/project?path={quote(path, safe='')}")

    page.get_by_role("button", name="Start a new research session", exact=True).click()
    page.get_by_role("button", name="Start new session #1", exact=True).click()
    session = page.locator("li[data-session-id]").first
    expect(session.locator(".session-status")).to_contain_text("running", timeout=15000)
    expect(session.locator(".session-row-content")).to_be_visible()
    form = session.locator(".human-intervention-form")
    expect(form).to_be_visible()
    feedback = session.locator("details.human-interventions")
    expect(feedback.locator("summary")).to_have_text("Human feedback")
    guidance_box = feedback.bounding_box()
    guidance_summary_box = feedback.locator("summary").bounding_box()
    assert (
        guidance_box
        and guidance_summary_box
        and guidance_summary_box["width"] >= guidance_box["width"] - 2
    )
    feedback.locator("summary").click()
    expect(form).to_be_hidden()
    feedback.locator("summary").click()
    expect(form).to_be_visible()
    type_options = form.locator(".human-intervention-type label")
    assert type_options.count() == 3
    type_y = [type_options.nth(index).bounding_box()["y"] for index in range(3)]
    assert type_y[0] < type_y[1] < type_y[2]
    recipients = form.locator(".human-intervention-target")
    expect(recipients).to_have_attribute("aria-label", "Feedback recipient")
    assert recipients.locator("legend").count() == 0
    recipient_options = recipients.locator("label")
    recipient_y = [recipient_options.nth(index).bounding_box()["y"] for index in range(2)]
    assert recipient_y[0] < recipient_y[1]
    assert type_y[0] == recipient_y[0]
    strategy_select = form.get_by_label("Strategy")
    strategy_label_box = form.locator(".human-intervention-strategy").bounding_box()
    assert strategy_label_box and type_y[0] == strategy_label_box["y"]
    strategy_box = strategy_select.bounding_box()
    form_box = form.bounding_box()
    assert strategy_box and form_box and 260 <= strategy_box["width"] <= 340
    assert strategy_box["x"] + strategy_box["width"] < form_box["x"] + form_box["width"] - 100
    controls = form.locator(":scope > *").evaluate_all(
        "els => els.slice(0, 3).map(el => el.className || el.tagName)"
    )
    assert controls == [
        "human-intervention-type",
        "human-intervention-target",
        "human-intervention-strategy",
    ]
    before = page.evaluate(
        """async ({path,id}) => {
          for (let attempt = 0; attempt < 100; attempt++) {
            const query = new URLSearchParams({path, fresh: String(Date.now())});
            const response = await fetch('/api/projects/research-sessions/' + id + '?' + query, {cache:'no-store'});
            const record = await response.json();
            if (record.calls_used >= 1) return record;
            await new Promise(resolve => setTimeout(resolve, 100));
          }
          throw new Error('The first provider step did not start');
        }""",
        {"path": path, "id": session.get_attribute("data-session-id")},
    )
    form.get_by_label("Objection").check()
    form.get_by_label("For skeptic").check()
    form.get_by_role("textbox", name="Feedback").fill(
        "Check whether the claimed recurrence also handles the initial boundary values."
    )
    add_feedback = form.get_by_role("button", name="Add", exact=True)
    expect(add_feedback).to_have_attribute(
        "aria-describedby", f"human-feedback-help-{session.get_attribute('data-session-id')}"
    )
    expect(
        form.locator("#human-feedback-help-" + session.get_attribute("data-session-id"))
    ).to_contain_text("Applies on a later call; no call starts now.")
    expect(form.locator(".human-intervention-submit small")).to_contain_text("no call starts now")
    add_feedback.click()
    expect(add_feedback).to_be_visible()

    session_id = session.get_attribute("data-session-id")
    accepted = page.evaluate(
        "async ({path,id}) => await (await fetch('/api/projects/research-sessions/' + id + '?' + new URLSearchParams({path}))).json()",
        {"path": path, "id": session_id},
    )
    assert accepted["calls_used"] == before["calls_used"], "Adding feedback must not call a model"
    intervention = accepted["interventions"][-1]
    assert intervention["status"] in {"queued", "delivered", "acknowledged"}
    assert intervention["target_strategy_ids"] == [strategy["id"]]
    assert set(intervention["target_roles"]) == {"skeptic"}

    expect(session.locator(".session-status")).to_have_text("ended", timeout=90000)
    final = page.evaluate(
        "async ({path,id}) => await (await fetch('/api/projects/research-sessions/' + id + '?' + new URLSearchParams({path}))).json()",
        {"path": path, "id": session_id},
    )
    intervention = next(item for item in final["interventions"] if item["id"] == intervention["id"])
    assert intervention["status"] == "acknowledged", intervention
    assert all(
        delivery["status"] == "acknowledged" and delivery["attempts"]
        for delivery in intervention["deliveries"]
    )
    assert all(
        delivery["target_cycle"] == delivery["attempts"][0]["cycle"]
        for delivery in intervention["deliveries"]
    )
    assert all(
        attempt.get("acknowledged_at") and attempt.get("uptake") and attempt.get("rationale")
        for delivery in intervention["deliveries"]
        for attempt in delivery["attempts"]
    )
    assert any(event["kind"] == "intervention.accepted" for event in final["events"])
    assert any(event["kind"] == "intervention.acknowledged" for event in final["events"])
    assert all(
        step["human_intervention_ids"]
        for step in final["steps"]
        if step["status"] == "completed"
        and any(
            delivery["status"] == "acknowledged"
            and step["id"] in [attempt["step_id"] for attempt in delivery["attempts"]]
            for delivery in intervention["deliveries"]
        )
    )

    page.screenshot(path="/tmp/sigma-t29-intervention-desktop.png", full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    page.reload()
    mobile_session = page.locator("li[data-session-id]").first
    expect(mobile_session.locator(".human-interventions")).to_be_visible()
    expect(mobile_session.locator(".human-intervention-history")).to_contain_text("cycle")
    overflow = page.evaluate(
        "document.documentElement.scrollWidth > document.documentElement.clientWidth"
    )
    assert not overflow, "Human-feedback UI must not create mobile horizontal overflow"
    assert not errors, errors
    page.screenshot(path="/tmp/sigma-t29-intervention-mobile.png", full_page=True)
    print(
        "PASS Chrome feedback controls, single-agent submission, no hidden call, acknowledgment and mobile layout"
    )
    browser.close()
