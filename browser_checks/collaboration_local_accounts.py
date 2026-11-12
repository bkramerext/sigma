"""Browser acceptance for local account-scoped collaboration against real APIs.

Two independent loopback mock-auth browser profiles exercise the production
workspace, ACL, revision and project persistence paths. No collaboration API
response is stubbed. Actual Google OAuth still requires manual smoke testing.
"""

from __future__ import annotations

import os
import secrets
import socket
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote
from urllib.request import urlopen
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OWNER = "mock-member-a@localhost.invalid"
COLLABORATOR = "mock-member-b@localhost.invalid"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for(url: str, process: subprocess.Popen, log: Path) -> None:
    for _ in range(100):
        if process.poll() is not None:
            raise AssertionError(f"Fixture exited: {log.read_text()[-3000:]}")
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except (OSError, TimeoutError):
            time.sleep(0.2)
    raise AssertionError(f"Fixture never became ready: {log.read_text()[-3000:]}")


def get_json(response) -> dict:
    data = response.json()
    assert isinstance(data, dict), data
    return data


def choose_difficulty(dialog, name: str) -> None:
    dialog.get_by_role("combobox", name="Difficulty").click()
    dialog.get_by_role("option", name=name).click()


def expand_saved_group(page) -> None:
    # Saved categories retain their collapsed state across navigations.
    group = page.locator("#recent-panel details.recent-type-group").first
    expect(group).to_be_visible()
    # The sticky account header can cover the category summary when Chrome
    # auto-scrolls it to the top. Disclosure behavior has independent tests;
    # expose its contents here to exercise the actual shared-project shortcut.
    group.evaluate("element => { element.open = true; }")
    expect(group).to_have_attribute("open", "")


def exercise(ui: str, workspaces: Path) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get(
                "SIGMA_BROWSER_EXECUTABLE",
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            ),
            headless=True,
        )
        owner_context = browser.new_context(viewport={"width": 1440, "height": 930})
        member_context = browser.new_context(viewport={"width": 1440, "height": 930})

        for context, identity, email in (
            (owner_context, "member-a", OWNER),
            (member_context, "member-b", COLLABORATOR),
        ):
            login = context.request.post(
                ui + "/api/cloud-auth/mock/select?identity=" + identity,
                headers={"Origin": ui},
            )
            assert login.status == 204, login.text()
            status = context.request.get(ui + "/api/cloud-auth/status")
            assert status.status == 200, status.text()
            assert get_json(status)["user"]["email"] == email

        owner = owner_context.new_page()
        member = member_context.new_page()
        title = "Local shared acceptance " + secrets.token_hex(4)
        created = owner_context.request.post(
            ui + "/api/projects/create",
            headers={"Origin": ui},
            data={
                "title": title,
                "problem": "Verify separate local accounts use one original project path.",
                "investigation_type": "mathematical",
            },
        )
        assert created.status == 201, created.text()
        project = get_json(created)
        path = project["path"]
        url = ui + "/project?path=" + quote(path, safe="")
        assert Path(path).is_dir() and (Path(path) / "project.json").is_file()

        # Member cannot see the owner's project before invitation.
        forbidden = member_context.request.get(ui + "/api/projects/inspect", params={"path": path})
        assert forbidden.status in {400, 401, 403, 404}, forbidden.text()
        before = get_json(member_context.request.get(ui + "/api/projects/recent"))
        assert all(item["path"] != path for item in before["projects"])

        owner.goto(url)
        owner.get_by_role("button", name="Project settings", exact=True).click()
        owner_dialog = owner.get_by_role("dialog", name="Project Settings")
        expect(owner_dialog.get_by_role("region", name="Collaborators")).to_be_visible()
        expect(owner_dialog.get_by_text(OWNER)).to_be_visible()
        assert owner_dialog.get_by_role("button", name=f"Remove {OWNER}").count() == 0
        # Project owner has real dropdowns, but neither displays hover text.
        for name in ("Research category", "Difficulty"):
            control = owner_dialog.get_by_role("combobox", name=name)
            expect(control).to_be_visible()
            expect(control).to_have_attribute("data-tooltip-disabled", "true")
            assert control.get_attribute("title") is None
        owner_dialog.get_by_role("button", name="Add collaborator").click()
        invite_input = owner_dialog.get_by_label("New collaborator email")
        invite_input.fill(COLLABORATOR)
        invite_input.press("Tab")
        expect(owner_dialog.get_by_text(COLLABORATOR)).to_be_visible()
        owner_dialog.get_by_role("button", name="Close Project Settings").click()
        expect(owner_dialog).not_to_be_visible()

        shared_response = owner_context.request.get(
            ui + "/api/projects/collaboration", params={"path": path}
        )
        assert shared_response.status == 200, shared_response.text()
        shared = get_json(shared_response)
        assert shared["owner"] == OWNER
        assert shared["collaborators"] == [COLLABORATOR]
        assert shared["revision"] >= 1

        permitted = member_context.request.get(ui + "/api/projects/inspect", params={"path": path})
        assert permitted.status == 200, permitted.text()
        assert get_json(permitted)["path"] == path
        recent = get_json(member_context.request.get(ui + "/api/projects/recent"))
        assert any(row["path"] == path and row["shared"] for row in recent["projects"])
        status = get_json(member_context.request.get(ui + "/api/cloud-auth/status"))
        member_root = workspaces / status["account"]["workspace"]["id"]
        assert not (member_root / Path(path).name).exists(), "No collaborator project copy"

        # N's own Saved tab must show the owner's project and group icon.
        member.goto(ui)
        member.get_by_role("tab", name="My Work").click()
        expand_saved_group(member)
        expect(
            member.get_by_role("button", name=f"Manage collaborators for {title}")
        ).to_be_visible()

        # The Users Round shortcut opens the owner's original project in Settings.
        owner.goto(ui)
        owner.get_by_role("tab", name="My Work").click()
        expand_saved_group(owner)
        shortcut = owner.get_by_role("button", name=f"Manage collaborators for {title}")
        expect(shortcut).to_be_visible()
        # Trigger the actual button handler without a sticky-header hit-test
        # race; the separate layout suite covers pointer positioning.
        shortcut.evaluate("element => element.click()")
        owner_dialog = owner.get_by_role("dialog", name="Project Settings")
        expect(owner_dialog.get_by_role("region", name="Collaborators")).to_be_visible()
        # Shared-project settings is a one-shot deep link, not persistent on refresh.
        assert owner.evaluate("new URL(location.href).searchParams.get('settings')") is None

        # An email deep link opens immediately only for the invited account.
        invitation_url = (
            url
            + "&invited_email="
            + quote(COLLABORATOR, safe="")
            + "&project_title="
            + quote(title, safe="")
        )
        member.goto(invitation_url)
        expect(member.get_by_role("button", name="Project settings", exact=True)).to_be_visible()
        expect(member.get_by_role("dialog", name="Open shared project")).to_have_count(0)

        # A different signed-in account is guided Home instead of getting
        # the raw Project unavailable/access-denied error.
        wrong_account = owner_context.new_page()
        wrong_account.goto(invitation_url)
        expect(wrong_account).to_have_url(ui + "/")
        welcome = wrong_account.get_by_role("dialog", name="Open shared project")
        expect(welcome).to_be_visible()
        expect(welcome.get_by_text(COLLABORATOR)).to_be_visible()
        expect(welcome.get_by_text(title, exact=True)).to_be_visible()
        expect(welcome.get_by_role("link", name="Sign in with Google")).to_have_attribute(
            "href", "/api/cloud-auth/login"
        )
        expect(wrong_account.get_by_text("Project unavailable")).to_have_count(0)
        welcome.get_by_role("button", name="Not now").click()
        expect(welcome).not_to_be_visible()
        wrong_account.close()

        # A signed-out visitor should see the same welcome, with an existing
        # sign-in/invitation route, before any project API request is made.
        guest_context = browser.new_context(viewport={"width": 1440, "height": 930})
        guest = guest_context.new_page()
        guest.goto(invitation_url)
        expect(guest).to_have_url(ui + "/")
        guest_welcome = guest.get_by_role("dialog", name="Open shared project")
        expect(guest_welcome).to_be_visible()
        expect(guest_welcome.get_by_text(COLLABORATOR)).to_be_visible()
        expect(guest_welcome.get_by_role("link", name="Sign in with Google")).to_be_visible()
        expect(guest_welcome.get_by_text("Request invitation")).to_have_count(0)

        # Simulate successful Google sign-in to the invited account without
        # leaving this browser context: its pending link should reopen itself.
        selected = guest_context.request.post(
            ui + "/api/cloud-auth/mock/select?identity=member-b",
            headers={
                "Origin": ui,
                "X-Sigma-Window": guest.evaluate("sessionStorage.getItem('sigma.auth.window')"),
            },
        )
        assert selected.status == 204, selected.text()
        guest.reload()
        expect(guest).to_have_url(url)
        expect(guest.get_by_role("button", name="Project settings", exact=True)).to_be_visible()
        guest_context.close()

        # Collaborators may edit the research description, but the owner
        # alone can change the project title.
        member.goto(url)
        expect(member.get_by_role("button", name="Edit project fields")).to_be_visible()
        member.get_by_role("button", name="Edit project fields").click()
        assert member.get_by_role("textbox", name="Project title").count() == 0
        expect(member.locator(".sigma-description-title-row .current-project")).to_have_text(title)
        expect(member.get_by_role("textbox", name="Research Problem")).to_be_visible()
        member.get_by_role("button", name="Cancel", exact=True).click()

        # Non-owners see values in the established field layout, not disabled
        # dropdowns that could be activated with a pointer or keyboard.
        member.goto(url)
        member.get_by_role("button", name="Project settings", exact=True).click()
        member_dialog = member.get_by_role("dialog", name="Project Settings")
        expect(member_dialog.get_by_role("region", name="Collaborators")).to_be_visible()
        assert member_dialog.get_by_role("combobox", name="Research category").count() == 0
        assert member_dialog.get_by_role("combobox", name="Difficulty").count() == 0
        readonly = member_dialog.locator(
            ".settings-classification-row .sigma-classification-readonly"
        )
        assert readonly.count() == 2
        expect(readonly.nth(0)).to_contain_text("Mathematics")
        expect(readonly.nth(1)).to_have_text("Medium")
        assert (
            member_dialog.locator(".settings-classification-row .research-type-chevron").count()
            == 0
        )
        expect(member_dialog.locator(".project-classification-readonly-note")).to_have_text(
            "Title, research category, difficulty, and user settings are inherited from the project owner."
        )
        # Pointer clicks and keyboard actions cannot open a listbox.
        readonly.nth(0).click()
        readonly.nth(1).click()
        member_dialog.press("ArrowDown")
        assert member_dialog.get_by_role("listbox", name="Research category").count() == 0
        assert member_dialog.get_by_role("listbox", name="Difficulty").count() == 0
        member_dialog.get_by_role("button", name="Close Project Settings").click()
        expect(member_dialog).not_to_be_visible()

        # A title saved by the owner must propagate to N's already-open window,
        # even when that browser tab is backgrounded.
        member.evaluate(
            """() => Object.defineProperty(document, 'visibilityState',
                {configurable: true, get: () => 'hidden'})"""
        )
        owner_dialog.get_by_role("button", name="Close Project Settings").click()
        owner.get_by_role("button", name="Edit project fields").click()
        # Editing keeps other Project actions visible but unmistakably gray.
        for action in (
            "Research Q/A",
            "Lean proof verification",
            "Export project",
            "Email project",
            "Project settings",
        ):
            button = owner.get_by_role("button", name=action, exact=True)
            expect(button).to_be_disabled()
            expect(button).to_have_css("opacity", "0.38")
        title = title + " renamed"
        owner.get_by_role("textbox", name="Project title").fill(title)
        owner.get_by_role("button", name="Save", exact=True).click()
        expect(owner.locator(".project-overview-card .current-project")).to_have_text(title)
        expect(member.locator(".project-overview-card .current-project")).to_have_text(
            title, timeout=20000
        )

        # The same authorization is enforced at the API boundary. Forged
        # classification requests must never change the stored project.
        from_view = get_json(
            member_context.request.get(ui + "/api/projects/inspect", params={"path": path})
        )
        initial_settings = {
            key: from_view["project"][key]
            for key in (
                "title",
                "problem",
                "desired_outcomes",
                "paper_requirements",
                "investigation_type",
                "ai_model",
                "reasoning_effort",
                "difficulty",
                "show_advanced_outcome_details",
            )
        }
        member_collaboration = get_json(
            member_context.request.get(ui + "/api/projects/collaboration", params={"path": path})
        )
        for field, forbidden_value in (
            ("investigation_type", "physics"),
            ("difficulty", "hard"),
            ("title", title + " unauthorized"),
        ):
            attempt = member_context.request.post(
                ui + "/api/projects/update",
                headers={"Origin": ui},
                data={
                    **initial_settings,
                    field: forbidden_value,
                    "path": path,
                    "expected": initial_settings,
                    "expected_revision": member_collaboration["revision"],
                    "collaborators": member_collaboration["collaborators"],
                },
            )
            assert attempt.status >= 400, (field, attempt.status, attempt.text())
            assert "Only the project owner" in attempt.text(), (field, attempt.text())
            still = get_json(
                owner_context.request.get(ui + "/api/projects/inspect", params={"path": path})
            )
            assert still["project"][field] == initial_settings[field], field

        # A non-owner can still edit the research subject. Keep Z's Settings
        # open: a remote save must update its contents without dismissing it.
        owner.get_by_role("button", name="Project settings", exact=True).click()
        owner_dialog = owner.get_by_role("dialog", name="Project Settings")
        expect(owner_dialog).to_be_visible()
        amended = "Research subject updated by collaborator"
        subject_update = member_context.request.post(
            ui + "/api/projects/update",
            headers={"Origin": ui},
            data={
                **initial_settings,
                "problem": amended,
                "path": path,
                "expected": initial_settings,
                "expected_revision": member_collaboration["revision"],
                "collaborators": member_collaboration["collaborators"],
            },
        )
        assert subject_update.status == 200, subject_update.text()
        updated = get_json(
            owner_context.request.get(ui + "/api/projects/inspect", params={"path": path})
        )
        assert updated["project"]["problem"] == amended, updated
        assert updated["project"]["difficulty"] == "medium", updated
        # Exercise the same open browser pair for another saved field update.
        expect(owner.locator(".project-overview-card")).to_contain_text(amended, timeout=20000)

        # Project Settings is a live view in both windows, not a stale editor
        # that is forcibly dismissed on every shared revision.
        expect(owner_dialog).to_be_visible(timeout=20000)
        expect(owner_dialog.get_by_role("combobox", name="Difficulty")).to_have_text("Medium")
        member.get_by_role("button", name="Project settings", exact=True).click()
        member_dialog = member.get_by_role("dialog", name="Project Settings")
        expect(member_dialog).to_be_visible()
        expect(member_dialog.locator(".settings-classification-row")).to_contain_text("Medium")
        with member.expect_response(
            lambda response: (
                response.url.split("?")[0].endswith("/api/projects/open")
                and response.request.method == "POST"
            ),
            timeout=20000,
        ) as refreshed:
            choose_difficulty(owner_dialog, "Hard")
        assert get_json(refreshed.value)["project"]["difficulty"] == "hard"
        expect(owner_dialog).to_be_visible()
        expect(member_dialog).to_be_visible()
        expect(member_dialog.locator(".settings-classification-row")).to_contain_text(
            "Hard", timeout=20000
        )
        updated = get_json(
            owner_context.request.get(ui + "/api/projects/inspect", params={"path": path})
        )
        assert updated["project"]["difficulty"] == "hard", updated

        # Category and collaborator changes must also appear in N's open dialog.
        category = owner_dialog.get_by_role("combobox", name="Research category")
        category.click()
        owner_dialog.get_by_role("option", name="Physics", exact=True).click()
        expect(member_dialog.locator(".settings-classification-row")).to_contain_text(
            "Physics", timeout=20000
        )
        expect(member_dialog).to_be_visible()
        category.click()
        owner_dialog.get_by_role("option", name="Mathematics", exact=True).click()
        expect(member_dialog.locator(".settings-classification-row")).to_contain_text(
            "Mathematics", timeout=20000
        )
        owner_dialog.get_by_role("button", name="Add collaborator").click()
        invite = owner_dialog.get_by_label("New collaborator email")
        invite.fill("third@example.org")
        invite.press("Tab")
        expect(member_dialog.get_by_text("third@example.org")).to_be_visible(timeout=20000)
        expect(member_dialog).to_be_visible()
        # Remove the temporary guest so later revoke-last-member coverage still
        # observes the project becoming private (no shared shortcut in My Work).
        owner_dialog.get_by_role("button", name="Remove third@example.org").click()
        expect(member_dialog.get_by_text("third@example.org")).to_have_count(0, timeout=20000)
        expect(member_dialog).to_be_visible()

        owner_dialog.get_by_role("button", name="Close Project Settings").click()
        member_dialog.get_by_role("button", name="Close Project Settings").click()
        expect(owner_dialog).not_to_be_visible()
        expect(member_dialog).not_to_be_visible()

        # Reuse the SAME N/Z browser profiles to test the entire shared Session
        # admission/control path against real auth, ACL and SQLite persistence.
        # Mock execution is provider-free but now follows real queue semantics.
        project_id = get_json(
            owner_context.request.get(ui + "/api/projects/inspect", params={"path": path})
        )["project"]["id"]
        strategy_response = get_json(
            owner_context.request.get(ui + "/api/projects/strategies", params={"path": path})
        )["strategies"]
        if strategy_response:
            strategy_id = strategy_response[0]["id"]
        else:
            made = owner_context.request.post(
                ui + "/api/projects/strategies",
                headers={"Origin": ui},
                data={
                    "path": path,
                    "title": "Concurrent collaborator research",
                    "approach": "Test independent ownership and queued capacity.",
                },
            )
            assert made.status == 201, made.text()
            strategy_id = get_json(
                owner_context.request.get(ui + "/api/projects/strategies", params={"path": path})
            )["strategies"][0]["id"]

        def submit_mock(context):
            return context.request.post(
                ui + "/api/projects/research-sessions/mock",
                headers={"Origin": ui},
                data={
                    "path": path,
                    "expected_project_id": project_id,
                    "strategy_id": strategy_id,
                    "idempotency_key": str(uuid4()),
                },
            )

        armed = owner_context.request.post(
            ui + "/api/__fixture/collaboration-arm-freeze-sessions",
            headers={"Origin": ui},
            data={"path": path},
        )
        assert armed.status == 200, armed.text()
        first_response = submit_mock(owner_context)
        second_response = submit_mock(member_context)
        assert first_response.status == 200, first_response.text()
        assert second_response.status == 200, second_response.text()
        first_run = get_json(first_response)
        second_run = get_json(second_response)
        assert first_run["id"] != second_run["id"]
        assert second_run["session_number"] == first_run["session_number"] + 1
        assert first_run["created_by"] == OWNER
        assert second_run["created_by"] == COLLABORATOR

        # Both mocks are initially queued. Explicitly advance the first run
        # once before freezing; otherwise this test races the browser's
        # background polling and can find no running run at all. The armed
        # stage-1 guard holds a running mock, so the probe cannot finish it.
        primed = owner_context.request.get(
            ui + "/api/projects/research-sessions", params={"path": path}
        )
        assert primed.status == 200, primed.text()
        assert any(run["status"] == "running" for run in get_json(primed)["sessions"]), (
            "Fixture failed to promote one queued mock before freezing"
        )
        held = owner_context.request.post(
            ui + "/api/__fixture/collaboration-freeze-sessions",
            headers={"Origin": ui},
            data={"path": path},
        )
        assert held.status == 200, held.text()
        # One project running slot: either creator may win; the other waits.
        # Do not impose deterministic ordering on legitimately concurrent jobs.
        status = get_json(
            owner_context.request.get(ui + "/api/projects/research-sessions", params={"path": path})
        )
        statuses = {item["id"]: item["status"] for item in status["sessions"]}
        assert {statuses[first_run["id"]], statuses[second_run["id"]]} == {
            "running",
            "queued",
        }, statuses

        # The same authenticated N/Z project windows must display every live
        # Session on its own tooltip line, with creator and queued/running state.
        for page in (owner, member):
            page.goto(url)
            page.wait_for_function(
                """({first, second, owner, member, firstStatus, secondStatus}) => {
                    const tip = document.querySelector('.project-header-title-action .research-running-indicator-frame')
                        ?.getAttribute('data-tooltip') || '';
                    const lines = tip.split('\\n').filter(Boolean);
                    return lines.length === 2
                        && lines.every(line => !line.includes('(running)'))
                        && lines.some(line => line.includes('Session ' + first)
                            && line.includes(owner) && line.includes(firstStatus))
                        && lines.some(line => line.includes('Session ' + second)
                            && line.includes(member) && line.includes(secondStatus));
                }""",
                arg={
                    "first": first_run["session_number"],
                    "second": second_run["session_number"],
                    "firstStatus": "" if statuses[first_run["id"]] == "running" else "(queued)",
                    "secondStatus": "" if statuses[second_run["id"]] == "running" else "(queued)",
                    "owner": OWNER,
                    "member": COLLABORATOR,
                },
                timeout=20000,
            )

        # Ask twice from different authenticated accounts while the two Session
        # runs remain active/queued. Hold fake provider calls (not the API or
        # storage) so both browser contexts must see four distinct activities.
        qa_questions = (
            "What research evidence can the owner corroborate?",
            "Which skeptic objections can the collaborator assess?",
        )
        request_ids = (uuid4().hex, uuid4().hex)
        # The public mock walkthrough route must keep refusing potential
        # provider calls. Only the import-guarded deterministic fixture alias
        # can exercise the actual Q/A handler in this acceptance run.
        prohibited = owner_context.request.post(
            ui + "/api/projects/research-qa",
            headers={"Origin": ui},
            data={
                "path": path,
                "expected_project_id": project_id,
                "expected_binding": "fixture:collaboration-qa",
                "question": qa_questions[0],
                "request_id": uuid4().hex,
            },
        )
        assert prohibited.status == 403, prohibited.text()
        assert get_json(prohibited).get("simulated") is True
        submit_qa = """({path, projectId, question, requestId}) => {
            window.sigmaCollaborationQA = fetch('/api/__fixture/collaboration-qa-ask', {
                method: 'POST', headers: {'Content-Type':'application/json'},
                body: JSON.stringify({
                    path, expected_project_id: projectId,
                    expected_binding: 'fixture:collaboration-qa',
                    question, request_id: requestId
                })
            }).then(async response => ({status: response.status, data: await response.json()}))
              .catch(error => ({status: 0, error: String(error)}));
        }"""
        for page, question, request_id in zip(
            (owner, member), qa_questions, request_ids, strict=True
        ):
            page.evaluate(
                submit_qa,
                {
                    "path": path,
                    "projectId": project_id,
                    "question": question,
                    "requestId": request_id,
                },
            )
        for _ in range(100):
            state = get_json(
                owner_context.request.get(ui + "/api/__fixture/collaboration-qa-state")
            )
            if state["started"] == 2:
                break
            time.sleep(0.1)
        else:
            # An early HTTP admission failure must be distinguished from a
            # provider-overlap timeout; surface actual browser responses.
            outcomes = [
                page.evaluate(
                    """async () => Promise.race([
                      window.sigmaCollaborationQA,
                      new Promise(resolve => setTimeout(() => resolve({pending: true}), 1000))
                    ])"""
                )
                for page in (owner, member)
            ]
            raise AssertionError(
                f"Both provider-free Q/A calls did not start: {state}; HTTP outcomes={outcomes}"
            )
        assert set(state["questions"]) == set(qa_questions), state

        # Same live activity endpoint under each identity, no faked UI response.
        for account, page in ((owner_context, owner), (member_context, member)):
            activity = account.request.get(
                ui + "/api/projects/activity-runs", params={"path": path}
            )
            assert activity.status == 200, activity.text()
            runs = get_json(activity)["runs"]
            assert len(runs) == 4, runs
            sessions = [run for run in runs if run["kind"] == "session"]
            answers = [run for run in runs if run["kind"] == "answer"]
            assert len(sessions) == len(answers) == 2, runs
            assert {run["creator"] for run in answers} == {OWNER, COLLABORATOR}, runs
            assert {run["status"] for run in sessions} == {"active", "queued"}, runs
            page.wait_for_function(
                """({owner, member}) => {
                    const tip = document.querySelector('.project-header-title-action .research-running-indicator-frame')
                        ?.getAttribute('data-tooltip') || '';
                    const lines = tip.split('\\n').filter(Boolean);
                    return lines.length === 4
                        && lines.filter(line => line.startsWith('Session ')).length === 2
                        && lines.filter(line => line.startsWith('Answer ')).length === 2
                        && lines.every(line => !line.includes('(running)'))
                        && lines.some(line => line.includes('(queued)'))
                        && lines.filter(line => line.includes(owner)).length === 2
                        && lines.filter(line => line.includes(member)).length === 2;
                }""",
                arg={"owner": OWNER, "member": COLLABORATOR},
                timeout=20000,
            )

        # A collaborator cannot piggyback on another creator's in-flight paid
        # request by reusing its request ID. Neither fixture call is duplicated.
        stolen = member_context.request.post(
            ui + "/api/__fixture/collaboration-qa-ask",
            headers={"Origin": ui},
            data={
                "path": path,
                "expected_project_id": project_id,
                "expected_binding": "fixture:collaboration-qa",
                "question": qa_questions[0],
                "request_id": request_ids[0],
            },
        )
        assert stolen.status >= 400, (stolen.status, stolen.text())
        assert (
            get_json(owner_context.request.get(ui + "/api/__fixture/collaboration-qa-state"))[
                "started"
            ]
            == 2
        )

        # Combine the two live Sessions and two held Q/A requests with two
        # independently admitted Papers. The real Paper gate serializes one
        # active generator and one queued generator; no provider is called.
        paper_runs = []
        for account in (owner_context, member_context):
            paper_response = account.request.post(
                ui + "/api/__fixture/collaboration-paper-start",
                headers={"Origin": ui},
                data={"path": path},
            )
            assert paper_response.status == 200, paper_response.text()
            paper_runs.append(get_json(paper_response))
        assert paper_runs[0]["run_id"] != paper_runs[1]["run_id"]
        assert paper_runs[1]["number"] == paper_runs[0]["number"] + 1
        # Cross-creator cancellation is forbidden even while queued. An
        # unauthorized release must leave both reservations and tasks intact.
        stolen_release = member_context.request.post(
            ui + "/api/__fixture/collaboration-paper-release",
            headers={"Origin": ui},
            data={"path": path, "run_id": paper_runs[0]["run_id"]},
        )
        assert stolen_release.status >= 400, stolen_release.text()

        for account, page in ((owner_context, owner), (member_context, member)):
            for _ in range(100):
                response = account.request.get(
                    ui + "/api/projects/activity-runs", params={"path": path}
                )
                assert response.status == 200, response.text()
                mixed = get_json(response)["runs"]
                paper_activity = [row for row in mixed if row["kind"] == "paper"]
                if len(mixed) == 6 and {row["status"] for row in paper_activity} == {
                    "active",
                    "queued",
                }:
                    break
                time.sleep(0.1)
            else:
                raise AssertionError(f"Expected six mixed activity rows: {mixed}")
            assert {row["creator"] for row in paper_activity} == {OWNER, COLLABORATOR}, mixed
            assert {row["number"] for row in paper_activity} == {
                item["number"] for item in paper_runs
            }, mixed
            page.wait_for_function(
                """({owner, member}) => {
                    const tip = document.querySelector('.project-header-title-action .research-running-indicator-frame')
                        ?.getAttribute('data-tooltip') || '';
                    const lines = tip.split('\\n').filter(Boolean);
                    return lines.length === 6
                        && lines.filter(line => line.startsWith('Session ')).length === 2
                        && lines.filter(line => line.startsWith('Paper ')).length === 2
                        && lines.filter(line => line.startsWith('Answer ')).length === 2
                        && lines.every(line => !line.includes('(running)'))
                        && lines.some(line => line.includes('(queued)'))
                        && lines.filter(line => line.includes(owner)).length === 3
                        && lines.filter(line => line.includes(member)).length === 3;
                }""",
                arg={"owner": OWNER, "member": COLLABORATOR},
                timeout=20000,
            )

        # Home's own green indicator lists all six independently attributed runs. A second tab
        # keeps both in-flight Q/A fetches attached to their original pages.
        homes = []
        for account in (owner_context, member_context):
            home = account.new_page()
            home.goto(ui)
            home.get_by_role("tab", name="My Work").click()
            expand_saved_group(home)
            indicator = home.get_by_role("button", name=f"Open active work in {title}")
            expect(indicator).to_be_visible(timeout=20000)
            home.wait_for_function(
                """({title, owner, member}) => {
                    const project = title;
                    const indicator = [...document.querySelectorAll(
                        'button.recent-activity-jump'
                    )].find(button => button.getAttribute('aria-label')
                        === 'Open active work in ' + project);
                    const lines = (indicator?.getAttribute('data-tooltip') || '').split('\\n')
                        .filter(Boolean);
                    return lines.every(line => !line.includes('(running)'))
                        && lines.some(line => line.includes('(queued)'))
                        && lines.length === 6
                        && lines.filter(line => line.startsWith('Session ')).length === 2
                        && lines.filter(line => line.startsWith('Paper ')).length === 2
                        && lines.filter(line => line.startsWith('Answer ')).length === 2
                        && lines.filter(line => line.includes(owner)).length === 3
                        && lines.filter(line => line.includes(member)).length === 3;
                }""",
                arg={"title": title, "owner": OWNER, "member": COLLABORATOR},
                timeout=20000,
            )
            homes.append(home)

        released = owner_context.request.post(
            ui + "/api/__fixture/collaboration-qa-release", headers={"Origin": ui}
        )
        assert released.status == 200, released.text()
        answers = []
        for page in (owner, member):
            outcome = page.evaluate("() => window.sigmaCollaborationQA")
            assert outcome["status"] == 200, outcome
            answers.append(outcome["data"])
        assert answers[0]["qa_id"] != answers[1]["qa_id"], answers
        assert answers[0]["created_by"] == OWNER, answers
        assert answers[1]["created_by"] == COLLABORATOR, answers
        all_answers = get_json(
            member_context.request.get(ui + "/api/projects/research-qa", params={"path": path})
        )["answers"]
        assert {record["created_by"] for record in all_answers} >= {OWNER, COLLABORATOR}
        assert {record["qa_id"] for record in all_answers} >= {
            answer["qa_id"] for answer in answers
        }
        # Creator/model attribution is inline metadata, not a smaller caption.
        # Exercise real Q/A cards under both independently authenticated users.
        for page in (owner, member):
            page.get_by_role("button", name="Research Q/A", exact=True).click()
            qa_dialog = page.get_by_role("dialog", name="Research Q/A")
            metadata = qa_dialog.locator(
                ".research-qa-library .saved-paper-meta .artifact-attribution"
            ).first
            expect(metadata).to_be_visible(timeout=20000)
            font_sizes = metadata.evaluate(
                """element => {
                    const current = Number.parseFloat(getComputedStyle(element).fontSize);
                    const parent = Number.parseFloat(
                        getComputedStyle(element.parentElement).fontSize
                    );
                    return [current, parent];
                }"""
            )
            assert font_sizes[0] == font_sizes[1], (
                "Q/A attribution must use the surrounding metadata font size",
                font_sizes,
            )
            qa_dialog.get_by_role("button", name="Close research Q/A").click()
        assert (
            get_json(owner_context.request.get(ui + "/api/__fixture/collaboration-qa-state"))[
                "started"
            ]
            == 2
        ), "No implicit provider retry is permitted"
        foreign_delete = member_context.request.delete(
            ui + f"/api/__fixture/collaboration-qa/{answers[0]['qa_id']}",
            params={"path": path},
            headers={"Origin": ui},
        )
        assert foreign_delete.status >= 400, foreign_delete.text()
        for account, paper in zip((owner_context, member_context), paper_runs, strict=True):
            released_paper = account.request.post(
                ui + "/api/__fixture/collaboration-paper-release",
                headers={"Origin": ui},
                data={"path": path, "run_id": paper["run_id"]},
            )
            assert released_paper.status == 200, released_paper.text()
        for home in homes:
            home.close()

        # Do not unfreeze synthetic per-read progression while both live
        # browser tabs are polling: they can finish the queued simulation
        # before the handoff assertion. Stop the current holder first, then
        # allow exactly the normal queued-to-running transition.
        running_id = next(
            run_id
            for run_id in (first_run["id"], second_run["id"])
            if statuses[run_id] == "running"
        )
        queued_id = second_run["id"] if running_id == first_run["id"] else first_run["id"]
        actors = {first_run["id"]: owner_context, second_run["id"]: member_context}
        for actor, foreign in (
            (owner_context, second_run["id"]),
            (member_context, first_run["id"]),
        ):
            forbidden = actor.request.post(
                ui + f"/api/projects/research-sessions/{foreign}/control",
                headers={"Origin": ui},
                data={"path": path, "action": "stop"},
            )
            assert forbidden.status >= 400, (forbidden.status, forbidden.text())
        # Stop only the current slot holder, regardless of which browser won.
        stopped = actors[running_id].request.post(
            ui + f"/api/projects/research-sessions/{running_id}/control",
            headers={"Origin": ui},
            data={"path": path, "action": "stop"},
        )
        assert stopped.status == 200, stopped.text()
        # Permit queued->running admission but continue holding stage-1 progress.
        # Otherwise two browser polls may finish the promoted mock before its
        # creator sends Stop, masking the handoff we intend to verify.
        armed_handoff = owner_context.request.post(
            ui + "/api/__fixture/collaboration-arm-freeze-sessions",
            headers={"Origin": ui},
            data={"path": path},
        )
        assert armed_handoff.status == 200, armed_handoff.text()
        visible = get_json(
            member_context.request.get(
                ui + "/api/projects/research-sessions", params={"path": path}
            )
        )["sessions"]
        latest = {item["id"]: item for item in visible}
        assert latest[running_id]["status"] == "stopped", latest
        assert latest[queued_id]["status"] == "running", latest
        assert latest[queued_id]["created_by"] == (
            OWNER if queued_id == first_run["id"] else COLLABORATOR
        )
        own_stop = actors[queued_id].request.post(
            ui + f"/api/projects/research-sessions/{queued_id}/control",
            headers={"Origin": ui},
            data={"path": path, "action": "stop"},
        )
        assert own_stop.status == 200, own_stop.text()
        unfrozen = owner_context.request.post(
            ui + "/api/__fixture/collaboration-unfreeze-sessions",
            headers={"Origin": ui},
        )
        assert unfrozen.status == 200, unfrozen.text()
        # Verify both creators' Stop checkpoints persist after unfreezing.
        check = {}
        for _attempt in range(30):
            check = get_json(
                owner_context.request.get(
                    ui + "/api/projects/research-sessions", params={"path": path}
                )
            )
            stopped_rows = [
                row for row in check["sessions"] if row["id"] in {first_run["id"], second_run["id"]}
            ]
            if len(stopped_rows) == 2 and all(row["status"] == "stopped" for row in stopped_rows):
                break
            time.sleep(0.1)
        assert {row["id"] for row in check["sessions"]} >= {
            first_run["id"],
            second_run["id"],
        }
        assert all(
            row["status"] == "stopped"
            for row in check["sessions"]
            if row["id"] in {first_run["id"], second_run["id"]}
        ), check
        # Owner catalog standards are projected into the SAVED shared project.
        # A member's own custom types/preferences must not override them.
        standards_before = get_json(owner_context.request.get(ui + "/api/project-types"))
        owner_custom = [
            entry for entry in standards_before["project_types"] if entry["user_defined"]
        ]
        owner_standards = "https://example.org/shared-research-743"
        owner_publication = "https://example.org/shared-publication-743"
        standards_saved = owner_context.request.put(
            ui + "/api/project-types",
            headers={"Origin": ui},
            data={
                "project_types": owner_custom,
                "expected_revision": standards_before["revision"],
                "builtin_custom_references": {
                    "mathematical": {
                        "research_standards_references": [
                            {"name": "Owner research standard", "url": owner_standards}
                        ],
                        "publication_standards_references": [
                            {"name": "Owner publication standard", "url": owner_publication}
                        ],
                    }
                },
            },
        )
        assert standards_saved.status == 200, standards_saved.text()
        owner_snapshot = get_json(
            owner_context.request.get(ui + "/api/projects/inspect", params={"path": path})
        )["project"]["project_type_snapshot"]
        member_snapshot = get_json(
            member_context.request.get(ui + "/api/projects/inspect", params={"path": path})
        )["project"]["project_type_snapshot"]
        assert member_snapshot == owner_snapshot
        after_standards = get_json(
            member_context.request.get(ui + "/api/projects/inspect", params={"path": path})
        )["project"]
        assert after_standards["problem"] == amended
        assert after_standards["difficulty"] == "hard"
        assert after_standards["title"] == title
        for field, fragment in (
            ("research_standards_references", "shared-research-743"),
            ("publication_standards_references", "shared-publication-743"),
        ):
            assert any(fragment in entry["url"] for entry in member_snapshot[field]), (
                field,
                member_snapshot[field],
            )
        member_types = get_json(member_context.request.get(ui + "/api/project-types"))
        assert not member_types["builtin_custom_references"].get("mathematical"), (
            "The owner's private type catalog leaked into a collaborator account"
        )

        # Submit TWO distinct Source Material additions before awaiting either
        # response: actual overlap across the existing signed-in N/Z browsers.
        owner_link = "https://example.org/owner-source-743"
        member_link = "https://example.org/member-source-743"
        submit_script = """({path, url}) => {
          window.sigmaSharedAdd = fetch('/api/projects/evidence/link', {
            method:'POST', headers:{'Content-Type':'application/json'},
            body:JSON.stringify({path, url})
          }).then(async r => ({status:r.status, data:await r.json()}))
            .catch(e => ({status:0, error:String(e)}));
        }"""
        owner.evaluate(submit_script, {"path": path, "url": owner_link})
        member.evaluate(submit_script, {"path": path, "url": member_link})
        owner_added = owner.evaluate("() => window.sigmaSharedAdd")
        member_added = member.evaluate("() => window.sigmaSharedAdd")
        assert owner_added["status"] == member_added["status"] == 200, (
            owner_added,
            member_added,
        )
        assert owner_added["data"]["id"] != member_added["data"]["id"]
        for account in (owner_context, member_context):
            sources = get_json(
                account.request.get(ui + "/api/projects/evidence", params={"path": path})
            )["files"]
            assert {owner_link, member_link} <= {
                entry.get("url") for entry in sources if entry.get("kind") == "link"
            }

        # Both *already open* project pages must show the other user's
        # committed addition; API visibility alone is not collaboration UI.
        for page, remote_link in ((owner, member_link), (member, owner_link)):
            project_toggle = page.get_by_role("button", name="Project", exact=True).first
            expect(project_toggle).to_be_visible()
            if project_toggle.get_attribute("aria-expanded") == "false":
                project_toggle.click()
            expect(page.locator(f'.sigma-supplied-evidence a[href="{remote_link}"]')).to_have_count(
                1, timeout=20000
            )

        duplicate = member_context.request.post(
            ui + "/api/projects/evidence/link",
            headers={"Origin": ui},
            data={"path": path, "url": owner_link},
        )
        assert duplicate.status == 200, duplicate.text()
        assert get_json(duplicate)["id"] == owner_added["data"]["id"]

        # Overlapping edit of ONE link must reject the stale write; it may
        # not replace another collaborator's committed change.
        revised_owner_link = "https://example.org/owner-source-revised-743"
        bypass = member_context.request.put(
            ui + f"/api/projects/evidence/{owner_added['data']['id']}/link",
            headers={"Origin": ui},
            data={"path": path, "url": "https://example.org/unversioned-source-743"},
        )
        assert bypass.status >= 400, bypass.text()
        assert "original URL" in bypass.text()
        # Start an inline edit in N, then have Z change that same link.
        # The committed update must cancel N's stale editor, never merge it.
        member_owner_row = member.locator(".sigma-evidence-row").filter(
            has=member.locator(f'a[href="{owner_link}"]')
        )
        member_owner_row.get_by_role("button", name="Edit Source Material link").click()
        expect(member.get_by_role("textbox", name="Source Material link")).to_be_visible()
        changed = owner_context.request.put(
            ui + f"/api/projects/evidence/{owner_added['data']['id']}/link",
            headers={"Origin": ui},
            data={
                "path": path,
                "url": revised_owner_link,
                "expected_url": owner_link,
            },
        )
        assert changed.status == 200, changed.text()
        expect(member.locator(".sigma-supplied-evidence")).to_contain_text(
            "This Source Material changed in another window. Your edit was cancelled.",
            timeout=20000,
        )
        expect(member.get_by_role("textbox", name="Source Material link")).to_have_count(0)
        stale = member_context.request.put(
            ui + f"/api/projects/evidence/{owner_added['data']['id']}/link",
            headers={"Origin": ui},
            data={
                "path": path,
                "url": "https://example.org/stale-source-743",
                "expected_url": owner_link,
            },
        )
        assert stale.status >= 400, stale.text()
        assert "changed by another collaborator" in stale.text()
        sources = get_json(
            member_context.request.get(ui + "/api/projects/evidence", params={"path": path})
        )["files"]
        assert any(entry.get("url") == revised_owner_link for entry in sources)
        assert not any(
            entry.get("url") == "https://example.org/stale-source-743" for entry in sources
        )

        # Identical PDFs uploaded by separate collaborators are de-duplicated
        # by their content hash rather than losing or duplicating the manifest.
        pdf = (ROOT / "tests/fixtures/sigma-valid-sample-paper.pdf").read_bytes()
        uploaded = []
        for account in (owner_context, member_context):
            result = account.request.post(
                ui + "/api/projects/evidence",
                headers={"Origin": ui, "Content-Type": "application/pdf"},
                params={"path": path, "filename": "shared-source-743.pdf"},
                data=pdf,
            )
            assert result.status == 200, result.text()
            uploaded.append(get_json(result))
        assert uploaded[0]["id"] == uploaded[1]["id"], uploaded
        sources = get_json(
            owner_context.request.get(ui + "/api/projects/evidence", params={"path": path})
        )["files"]
        assert sum(entry.get("sha256") == uploaded[0]["sha256"] for entry in sources) == 1

        owner.get_by_role("button", name="Project settings", exact=True).click()
        owner_dialog = owner.get_by_role("dialog", name="Project Settings")
        owner_dialog.get_by_role("button", name=f"Remove {COLLABORATOR}").click()
        owner_dialog.get_by_role("button", name="Close Project Settings").click()
        expect(owner_dialog).not_to_be_visible()

        # Revocation must be enforced by the server, not just by a hidden icon.
        revoked = member_context.request.get(ui + "/api/projects/inspect", params={"path": path})
        assert revoked.status in {400, 401, 403, 404}, revoked.text()
        recent = get_json(member_context.request.get(ui + "/api/projects/recent"))
        assert all(row["path"] != path for row in recent["projects"])
        owner.goto(ui)
        owner.get_by_role("tab", name="My Work").click()
        expand_saved_group(owner)
        expect(owner.get_by_role("button", name=f"Manage collaborators for {title}")).to_have_count(
            0
        )
        assert Path(path).is_dir() and (Path(path) / "project.json").is_file(), (
            "Revocation must not move or delete the owner's project"
        )

        # The My Work X for an invited collaborator must actually revoke
        # membership, not merely hide the recent entry until the next poll.
        owner.goto(url)
        owner.get_by_role("button", name="Project settings", exact=True).click()
        owner_dialog = owner.get_by_role("dialog", name="Project Settings")
        owner_dialog.get_by_role("button", name="Add collaborator").click()
        invite = owner_dialog.get_by_label("New collaborator email")
        invite.fill(COLLABORATOR)
        invite.press("Tab")
        owner_dialog.get_by_role("button", name="Close Project Settings").click()
        member.goto(ui)
        member.get_by_role("tab", name="My Work").click()
        expand_saved_group(member)
        leave = member.get_by_role("button", name="Stop collaborating on this project")
        expect(leave).to_be_visible()
        leave.click()
        confirm = member.get_by_role("group", name=f"Confirm remove {title}")
        confirm.get_by_role("button", name="Confirm").click()
        expect(leave).to_have_count(0)
        after_leave = member_context.request.get(
            ui + "/api/projects/inspect", params={"path": path}
        )
        assert after_leave.status in {400, 401, 403, 404}, after_leave.text()
        owner_membership = get_json(
            owner_context.request.get(ui + "/api/projects/collaboration", params={"path": path})
        )
        assert COLLABORATOR not in owner_membership["collaborators"]
        assert Path(path).is_dir() and (Path(path) / "project.json").is_file(), (
            "Leaving must not delete the owner's project"
        )

        verify_new_windows_inherit_latest_google_account(browser, ui)
        owner_context.close()
        member_context.close()
        browser.close()


def verify_new_windows_inherit_latest_google_account(browser, ui: str) -> None:
    """One browser profile: each existing window stays put, a new one gets latest."""
    context = browser.new_context(viewport={"width": 1440, "height": 930})
    try:

        def open_window():
            page = context.new_page()
            page.goto(ui)
            page.wait_for_function(
                "window.sessionStorage.getItem('sigma.auth.windowScoped') === 'yes'"
            )
            return page

        def account(page):
            return page.evaluate(
                """async () => {
                  const response = await fetch('/api/cloud-auth/status', {cache: 'no-store'});
                  const status = await response.json();
                  return status.user?.email ?? null;
                }"""
            )

        def sign_in(page, identity):
            code = page.evaluate(
                """async identity => {
                  const response = await fetch('/api/cloud-auth/mock/select?identity='
                    + encodeURIComponent(identity), {method: 'POST'});
                  return response.status;
                }""",
                identity,
            )
            assert code == 204, code
            page.reload()

        first = open_window()
        assert account(first) is None
        sign_in(first, "member-a")
        assert account(first) == OWNER

        # New windows pin the most recent sign-in, but existing windows
        # retain their identities when another one switches accounts.
        second = open_window()
        assert account(second) == OWNER
        first_id = first.evaluate("sessionStorage.getItem('sigma.auth.window')")
        second_id = second.evaluate("sessionStorage.getItem('sigma.auth.window')")
        assert first_id != second_id
        sign_in(second, "member-b")
        assert account(second) == COLLABORATOR
        assert account(first) == OWNER

        third = open_window()
        assert account(third) == COLLABORATOR

        # window.open can copy sessionStorage. The child must get its own ID.
        with first.expect_popup() as popup_info:
            first.evaluate("window.open('/', '_blank')")
        popup = popup_info.value
        popup.wait_for_load_state("domcontentloaded")
        popup.wait_for_function(
            "previous => window.sessionStorage.getItem('sigma.auth.window') !== previous",
            arg=first_id,
        )
        popup.wait_for_function(
            "window.sessionStorage.getItem('sigma.auth.windowScoped') === 'yes'"
        )
        assert popup.evaluate("sessionStorage.getItem('sigma.auth.window')") != first_id
        assert account(popup) == COLLABORATOR
        assert account(first) == OWNER

        # The first actual pill click in a newly opened window must log out,
        # even when the auxiliary research-preservation request is unavailable.
        # Previously that failure aborted the click before logout was attempted.
        third.route(
            "**/api/projects/research-presence/auth-handoff",
            lambda route: route.fulfill(
                status=503,
                content_type="application/json",
                body='{"error":"Temporary handoff failure"}',
            ),
        )
        logout_requests = []
        third.on(
            "request",
            lambda request: (
                logout_requests.append(request)
                if request.url.endswith("/api/cloud-auth/logout")
                else None
            ),
        )
        third.get_by_role("button", name="Sign out of Google", exact=True).click()
        expect(third.get_by_role("link", name="Sign in with Google")).to_be_visible()
        assert len(logout_requests) == 1
        assert account(third) is None
        assert account(first) == OWNER
        assert account(second) == COLLABORATOR
        assert account(popup) == COLLABORATOR

        # Signing out the most recent login leaves existing pinned sessions
        # untouched but means a future new window starts signed out.
        code = second.evaluate(
            """async () => (await fetch('/api/cloud-auth/logout', {method: 'POST'})).status"""
        )
        assert code == 204
        second.reload()
        assert account(second) is None
        assert account(first) == OWNER
        assert account(third) is None
        assert account(popup) == COLLABORATOR
        fourth = open_window()
        assert account(fourth) is None
    finally:
        context.close()


def main() -> None:
    api_port, ui_port = free_port(), free_port()
    while api_port == ui_port:
        ui_port = free_port()
    api, ui = f"http://127.0.0.1:{api_port}", f"http://127.0.0.1:{ui_port}"
    with TemporaryDirectory(prefix="sigma-local-collaboration-") as temporary:
        root = Path(temporary)
        auth, workspaces, projects, state = (
            root / "auth",
            root / "workspaces",
            root / "projects",
            root / "state",
        )
        for folder in (auth, workspaces, projects, state):
            folder.mkdir(mode=0o700)
        env = os.environ.copy()
        env.update(
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_MOCK_AUTH": "1",
                "SIGMA_LOCAL_AUTO_ADMIN": "false",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": ui,
                "GOOGLE_OIDC_CLIENT_ID": "fixture.apps.googleusercontent.com",
                "GOOGLE_OIDC_CLIENT_SECRET": "fixture-secret",
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "fixture-admin@example.org",
                "SIGMA_CLOUD_AUTH_HOME": str(auth),
                "SIGMA_CLOUD_WORKSPACES_ROOT": str(workspaces),
                "SIGMA_PROJECTS_ROOT": str(projects),
                "SIGMA_STATE_DIR": str(state),
                "SIGMA_API_TARGET": api,
            }
        )
        api_log, ui_log = root / "api.log", root / "ui.log"
        processes: list[subprocess.Popen] = []
        with api_log.open("w") as api_output, ui_log.open("w") as ui_output:
            try:
                backend = subprocess.Popen(
                    [
                        str(ROOT / ".venv/bin/python"),
                        "-m",
                        "uvicorn",
                        "collaboration_provider_fixture:app",
                        "--app-dir",
                        str(ROOT / "browser_checks"),
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(api_port),
                        "--log-level",
                        "warning",
                    ],
                    cwd=ROOT,
                    env=env,
                    stdout=api_output,
                    stderr=subprocess.STDOUT,
                )
                processes.append(backend)
                wait_for(api + "/api/ui-instance", backend, api_log)
                frontend = subprocess.Popen(
                    [
                        "npm",
                        "--prefix",
                        str(ROOT / "frontend"),
                        "run",
                        "dev",
                        "--",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(ui_port),
                        "--strictPort",
                    ],
                    cwd=ROOT,
                    env=env,
                    stdout=ui_output,
                    stderr=subprocess.STDOUT,
                )
                processes.append(frontend)
                wait_for(ui + "/", frontend, ui_log)
                exercise(ui, workspaces)
            except BaseException:
                print("Backend log:\n", api_log.read_text()[-5000:])
                print("Frontend log:\n", ui_log.read_text()[-5000:])
                raise
            finally:
                for process in reversed(processes):
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
    print(
        "PASS local browser collaboration: identity isolation, one original path, "
        "membership, shared shortcut, concurrent edits, stale-save rejection, revocation"
    )


if __name__ == "__main__":
    main()
