"""Exercise the fake admin UI in real Chrome without Google OAuth or paid calls.

Start SIGMA with: ./sigma start --admin
Then run: uv run --with playwright python browser_checks/t22_admin_preview.py
"""
import os
from playwright.sync_api import sync_playwright, expect

URL = "http://127.0.0.1:5173"

def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get(
                "SIGMA_BROWSER_EXECUTABLE",
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            ),
            headless=True,
        )
        try:
            page = browser.new_page()
            page.goto(URL, wait_until="networkidle")
            page.get_by_role("button", name="Access Management").click()
            dialog = page.get_by_role("dialog", name="Access Management")
            expect(dialog).to_be_visible()
            expect(dialog.get_by_text("Local admin preview.", exact=False)).to_be_visible()
            dialog.get_by_label("Email address", exact=True).fill("preview@example.org")
            dialog.get_by_role("button", name="Add authorization").click()
            expect(dialog.get_by_text("preview@example.org", exact=True)).to_be_visible()
            row = dialog.locator("li", has=dialog.get_by_text("preview@example.org", exact=True))
            row.get_by_role("spinbutton", name="Allowance for preview@example.org").fill("4.5")
            row.get_by_role("button", name="Save allowance").click()
            expect(row).to_contain_text("effective allowance $4.50")
            row.get_by_role("button", name="Revoke").click()
            expect(row.get_by_text("revoked", exact=False)).to_be_visible()
            # The production API is untouched by the fake administrator.
            response = page.request.get("http://127.0.0.1:8000/api/cloud-auth/status")
            assert response.ok
            assert response.json()["enabled"] is False, response.text()
            print("Admin preview: fake grant/revoke and backend isolation PASS")
        finally:
            browser.close()

if __name__ == "__main__":
    main()
