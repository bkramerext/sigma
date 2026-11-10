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
        assert Path(path).is_file()

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
        assert any(
            row["path"] == path and row["shared"] and row["collaborating"]
            for row in recent["projects"]
        )
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

        # Opening Project Settings from a shared-project shortcut is one-shot;
        # refreshing the same project must not reopen the dialog.
        member.goto(url + "&settings=collaborators")
        settings_once = member.get_by_role("dialog", name="Project Settings")
        expect(settings_once).to_be_visible()
        expect(member).to_have_url(url)
        member.reload()
        expect(member.get_by_role("dialog", name="Project Settings")).to_have_count(0)

        # Preserve the original owner's staged settings for conflict testing.
        # Concurrent settings: a collaborator can edit the same file, while
        # the owner's stale draft must fail revision CAS, not overwrite it.
        member.goto(url)
        member.get_by_role("button", name="Project settings", exact=True).click()
        member_dialog = member.get_by_role("dialog", name="Project Settings")
        expect(member_dialog.get_by_role("region", name="Collaborators")).to_be_visible()
        choose_difficulty(member_dialog, "Hard")
        member_dialog.get_by_role("button", name="Close Project Settings").click()
        expect(member_dialog).not_to_be_visible()
        updated = get_json(
            owner_context.request.get(ui + "/api/projects/inspect", params={"path": path})
        )
        assert updated["project"]["difficulty"] == "hard", updated

        choose_difficulty(owner_dialog, "Easy")
        expect(owner_dialog.locator(".error")).to_contain_text("saved by")
        expect(owner_dialog.get_by_role("combobox", name="Difficulty")).to_have_text("Easy")
        # A stale draft remains visible for review, but cannot overwrite the
        # collaborator's newer change. Reopen the original for a clean editor.
        owner.goto(url)
        expect(owner_dialog).not_to_be_visible()

        # Settings deep links are consumed and a reload stays in the project.
        owner.goto(url)
        owner.get_by_role("button", name="Project settings", exact=True).click()
        owner_dialog = owner.get_by_role("dialog", name="Project Settings")
        expect(owner_dialog.get_by_role("combobox", name="Difficulty")).to_have_text("Hard")
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
        assert Path(path).is_file(), "Revocation must not move or delete the owner's project"

        # Reinvite N to test the My Work X as real membership removal.
        owner.goto(url)
        owner.get_by_role("button", name="Project settings", exact=True).click()
        owner_dialog = owner.get_by_role("dialog", name="Project Settings")
        owner_dialog.get_by_role("button", name="Add collaborator").click()
        invite_input = owner_dialog.get_by_label("New collaborator email")
        invite_input.fill(COLLABORATOR)
        invite_input.press("Tab")
        owner_dialog.get_by_role("button", name="Close Project Settings").click()

        member.goto(ui)
        member.get_by_role("tab", name="My Work").click()
        expand_saved_group(member)
        project_entry = member.locator(".recent-entry").filter(
            has=member.get_by_role("button", name=title, exact=True)
        )
        exit_button = project_entry.get_by_role(
            "button", name="Stop collaborating on this project"
        )
        expect(exit_button).to_have_attribute(
            "data-tooltip", "Stop collaborating on this project"
        )
        exit_button.click()
        project_entry.get_by_role("button", name="Confirm", exact=True).click()
        expect(
            member.get_by_role("button", name=f"Manage collaborators for {title}")
        ).to_have_count(0)
        after_leave = get_json(owner_context.request.get(
            ui + "/api/projects/collaboration", params={"path": path}
        ))
        assert COLLABORATOR not in after_leave["collaborators"], after_leave
        assert Path(path).is_file(), "Leaving a project must not delete its research"
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

        # Signing out the most recent login leaves existing pinned sessions
        # untouched but means a future new window starts signed out.
        code = second.evaluate(
            """async () => (await fetch('/api/cloud-auth/logout', {method: 'POST'})).status"""
        )
        assert code == 204
        second.reload()
        assert account(second) is None
        assert account(first) == OWNER
        assert account(third) == COLLABORATOR
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
                        "sigma.api:app",
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
