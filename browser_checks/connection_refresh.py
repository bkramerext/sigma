"""Controlled-clock health refresh lifecycle checks in real Chrome."""

import os

from playwright.sync_api import expect, sync_playwright

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    page = browser.new_page(viewport={"width": 1280, "height": 720})
    page.add_init_script(
        """
        (() => {
          const realNow = Date.now.bind(Date);
          const realSetTimeout = window.setTimeout.bind(window);
          const realClearTimeout = window.clearTimeout.bind(window);
          window.__fakeNow = Date.UTC(2030, 0, 1);
          window.__visible = true;
          window.__healthTimers = [];
          window.__connectionRequests = 0;
          window.__activeAccount = 'fixture-account';
          window.__welcomeAcks = 0;
          window.__welcomePending = localStorage.getItem('fixture-welcome-acked') !== 'yes';
          window.__holdNext = false;
          window.__nextFailure = false;
          window.__pendingChecks = [];
          Date.now = () => window.__fakeNow;
          Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => window.__visible ? 'visible' : 'hidden' });
          window.setTimeout = (callback, delay = 0, ...args) => {
            if (delay >= 10000 && delay <= 300000) {
              const record = { callback, delay, cancelled: false };
              window.__healthTimers.push(record);
              return record;
            }
            return realSetTimeout(callback, delay, ...args);
          };
          window.clearTimeout = (timer) => {
            if (timer && typeof timer === 'object' && 'cancelled' in timer) timer.cancelled = true;
            else realClearTimeout(timer);
          };
          window.__nextTimer = () => window.__healthTimers.find(timer => !timer.cancelled);
          window.__fireTimer = () => {
            const timer = window.__nextTimer();
            if (!timer) throw new Error('No scheduled connection health timer');
            timer.cancelled = true;
            timer.callback();
            return timer.delay;
          };
          window.__setVisible = (visible) => {
            window.__visible = visible;
            document.dispatchEvent(new Event('visibilitychange'));
          };
          const realFetch = window.fetch.bind(window);
          window.fetch = (input, init = {}) => {
            const url = typeof input === 'string' ? input : input.url;
            if (url.startsWith('/api/ai/connection?')) {
              window.__connectionRequests++;
              const connected = !!window.__activeAccount;
              const body = {
                mode: 'chatgpt', status: connected ? 'connected' : 'disconnected',
                label: connected ? 'ChatGPT connected' : 'Connect AI',
                guidance: connected ? 'Plan connection verified.' : 'Connect your ChatGPT account.',
                checked_at: connected ? new Date(window.__fakeNow).toISOString() : null,
                ttl_seconds: 60, account_label: connected ? 'test@example.test' : null,
                active_account: window.__activeAccount,
                accounts: connected ? [{ id: 'fixture-account', label: 'test@example.test' }] : [],
                welcome_pending: window.__welcomePending
              };
              return new Promise((resolve, reject) => {
                const finish = () => {
                  if (window.__nextFailure) {
                    window.__nextFailure = false;
                    reject(new TypeError('Failed to fetch'));
                    return;
                  }
                  resolve(new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } }));
                };
                if (window.__holdNext) { window.__holdNext = false; window.__pendingChecks.push(finish); }
                else finish();
              });
            }
            if (url === '/api/ai/welcome' && init.method === 'POST') {
              window.__welcomeAcks++;
              window.__welcomePending = false;
              localStorage.setItem('fixture-welcome-acked', 'yes');
              return Promise.resolve(new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } }));
            }
            if (url === '/api/ai/disconnect' && init.method === 'POST') {
              window.__activeAccount = null;
              return Promise.resolve(new Response(JSON.stringify({ message: 'Disconnected locally.', remote_revocation_confirmed: true }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
            }
            return realFetch(input, init);
          };
          window.__releaseCheck = () => { const finish = window.__pendingChecks.shift(); if (!finish) throw new Error('No held connection check'); finish(); };
        })();
        """
    )
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto("http://127.0.0.1:5173/")
    status = page.get_by_role("status")
    expect(status.filter(has_text="ChatGPT connected")).to_be_visible()
    expect(page.get_by_text("You're using your ChatGPT plan", exact=True)).to_be_visible()
    assert page.evaluate("window.__welcomeAcks") == 1
    assert page.evaluate("window.__connectionRequests") == 1
    assert page.evaluate("window.__nextTimer().delay") == 48000

    page.evaluate("window.__holdNext = true; window.__fakeNow += 48000; window.__fireTimer()")
    page.wait_for_function("window.__connectionRequests === 2")
    expect(status.filter(has_text="ChatGPT connected")).to_be_visible()
    assert not status.filter(has_text="Checking AI").count()
    page.evaluate("window.__releaseCheck()")
    page.wait_for_function("window.__nextTimer() !== undefined")
    expect(status.filter(has_text="ChatGPT connected")).to_be_visible()
    assert page.evaluate("window.__nextTimer().delay") == 48000
    page.evaluate("window.__fakeNow += 48000; window.__fireTimer()")
    page.wait_for_function("window.__connectionRequests === 3")
    expect(status.filter(has_text="ChatGPT connected")).to_be_visible()
    page.wait_for_function("window.__nextTimer() !== undefined")
    assert page.evaluate("window.__nextTimer().delay") == 48000

    # Hidden time causes no requests; becoming visible after TTL coalesces one check.
    page.evaluate("window.__setVisible(false); window.__fakeNow += 61000")
    assert not page.evaluate("window.__nextTimer()")
    assert page.evaluate("window.__connectionRequests") == 3
    page.evaluate("window.__setVisible(true)")
    page.wait_for_function("window.__connectionRequests === 4")
    expect(status.filter(has_text="ChatGPT connected")).to_be_visible()
    assert page.evaluate("window.__welcomeAcks") == 1

    # A transient network failure removes green status and schedules capped backoff.
    page.evaluate("window.__nextFailure = true; window.__fakeNow += 48000; window.__fireTimer()")
    page.wait_for_function(
        "document.querySelector('[role=status]')?.textContent.includes('AI status unavailable')"
    )
    expect(status.filter(has_text="AI status unavailable")).to_be_visible()
    page.get_by_label("AI connection settings", exact=True).click()
    popover = page.locator(".connection-details")
    expect(popover.get_by_text("Connection status could not be refreshed.")).to_be_visible()
    expect(popover.get_by_role("button", name="Retry connection", exact=True)).to_be_enabled()
    assert page.evaluate("window.__nextTimer().delay") == 30000
    for width, height in ((1280, 720), (390, 844), (320, 844)):
        page.set_viewport_size({"width": width, "height": height})
        expect(status.filter(has_text="AI status unavailable")).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        expect(popover.get_by_role("button", name="Retry connection", exact=True)).to_be_visible()
    page.set_viewport_size({"width": 1280, "height": 720})

    # Retry from the popover is explicit and immediately restores the verified state.
    page.evaluate("window.__holdNext = true")
    popover.get_by_role("button", name="Retry connection", exact=True).click()
    expect(popover.get_by_role("button", name="Checking…", exact=True)).to_be_visible()
    assert page.evaluate("window.__connectionRequests") == 6
    assert not status.filter(has_text="Checking AI").count()
    page.evaluate("window.__releaseCheck()")
    expect(status.filter(has_text="ChatGPT connected")).to_be_visible()
    assert page.evaluate("window.__welcomeAcks") == 1
    page.reload()
    expect(status.filter(has_text="ChatGPT connected")).to_be_visible()
    assert not page.get_by_text("You're using your ChatGPT plan", exact=True).count()
    assert page.evaluate("window.__welcomeAcks") == 0
    assert page.evaluate("window.__connectionRequests") == 1

    # A late successful result from the old account cannot undo an explicit Disconnect.
    page.get_by_label("AI connection settings", exact=True).click()
    page.evaluate("window.__holdNext = true; window.__fakeNow += 48000; window.__fireTimer()")
    page.wait_for_function("window.__connectionRequests === 2")
    page.locator(".connection-details").get_by_role("button", name="Disconnect", exact=True).click()
    page.wait_for_function("window.__connectionRequests === 3")
    expect(status.filter(has_text="Connect AI")).to_be_visible()
    page.evaluate("window.__releaseCheck()")
    expect(status.filter(has_text="Connect AI")).to_be_visible()
    assert not status.filter(has_text="ChatGPT connected").count()
    assert not errors, errors
    print(
        "PASS 48s shared health refresh, stable header during pending work, hidden-tab pause/resume, transient failure/backoff/manual retry, stale response rejected after Disconnect, one-time welcome across refresh and reload"
    )
    browser.close()
