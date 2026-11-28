"""Provider-free Chromium checks for transcript navigation and stale async work."""

import os

from playwright.sync_api import expect, sync_playwright

URL = os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173").rstrip("/")


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get(
                "SIGMA_BROWSER_EXECUTABLE", playwright.chromium.executable_path
            ),
            headless=True,
        )
        page = browser.new_page(viewport={"width": 1200, "height": 900})
        # Fail closed: not even an unexpected request can reach a paid converter.
        page.route("**/api/projects/text/convert", lambda route: route.abort())
        page.goto(URL, wait_until="domcontentloaded")
        page.evaluate(
            """async () => {
                const React = (await import('/node_modules/.vite/deps/react.js')).default;
                const ReactDOM = await import('/node_modules/.vite/deps/react-dom_client.js');
                // Vite's optimized CommonJS dependency may expose only a default export.
                const createRoot = ReactDOM.createRoot ?? ReactDOM.default?.createRoot;
                if (typeof createRoot !== 'function')
                    throw new Error('React DOM createRoot unavailable in browser fixture');
                const { default: SessionLogPage } = await import('/src/SessionLogPage.tsx');
                const host = document.createElement('main');
                document.body.replaceChildren(host);
                const root = createRoot(host);
                const stamp = '2026-01-01T00:00:00Z';
                const id = 'shared-request';
                const originalFetch = window.fetch.bind(window);
                const fixture = {
                    mode: 'holdConfig', configs: 0, conversions: 0,
                    oldPolls: [], pendingConfig: null, pendingConversion: null,
                };
                const snapshot = name => {
                    const text = name === 'a'
                        ? 'Session A accepted original text for a sufficiently long result.'
                        : 'Session B accepted original text for a sufficiently long result.';
                    const saved = {
                        step_id: 'shared-step', request_id: id,
                        role: 'investigator', strategy_id: 'strategy', round: 1,
                        status: 'completed', text, finished_at: stamp,
                        content_digest: 'fixture-digest-' + name,
                    };
                    return {
                        events: [{
                            seq: 1, timestamp: stamp, type: 'provider_response',
                            step_id: 'shared-step', request_id: id,
                            response: { output_text: text },
                        }],
                        transcript_responses: {
                            '1': { text, content_digest: 'fixture-digest-' + name },
                        },
                        cursor: 1, project_id: 'project-' + name,
                        project_title: 'Fixture ' + name.toUpperCase(),
                        short_name: 'Fixture ' + name.toUpperCase(),
                        session: { number: name === 'a' ? 1 : 2, status: 'running' },
                        transcript_state_version: 'version-' + name,
                        transcript_state: name === 'a' ? [saved] : [
                            saved, {
                                step_id: 'missing-reply', role: 'skeptic',
                                strategy_id: 'strategy', round: 1, status: 'completed',
                                text: 'Session B saved critique without a retained raw reply.',
                            },
                        ],
                    };
                };
                window.fetch = async (input, init) => {
                    const url = new URL(typeof input === 'string' ? input : input.url, location.origin);
                    if (url.pathname.endsWith('/log')) {
                        const name = url.pathname.includes('/a/log') ? 'a' : 'b';
                        if (name === 'a' && url.searchParams.get('after') !== '0') {
                            // Deliberately ignore abort to exercise the stale-response guard.
                            return new Promise(resolve => fixture.oldPolls.push(
                                () => resolve(Response.json(snapshot('a')))
                            ));
                        }
                        return Response.json(snapshot(name));
                    }
                    if (url.pathname.endsWith('/proposals/config')
                        && url.searchParams.get('purpose') === 'markdown') {
                        fixture.configs++;
                        const config = () => Response.json({available: true, binding: 'fixture'});
                        if (fixture.mode === 'holdConfig')
                            return new Promise(resolve => {
                                fixture.pendingConfig = () => resolve(config());
                            });
                        return config();
                    }
                    if (url.pathname === '/api/projects/text/convert') {
                        fixture.conversions++;
                        return new Promise(resolve => {
                            fixture.pendingConversion = () => resolve(Response.json({
                                body: 'STALE CONVERSION MUST NEVER APPEAR',
                            }));
                        });
                    }
                    return originalFetch(input, init);
                };
                fixture.navigate = name => {
                    history.replaceState(null, '', '?session_log=' + name + '&path=/fixture/' + name);
                    root.render(React.createElement(SessionLogPage));
                };
                window.transcriptFixture = fixture;
                fixture.navigate('a');
            }"""
        )
        accepted = page.locator('[data-transcript-entry="response-shared-request"]')
        markdown = accepted.locator(".session-transcript-entry-markdown")
        expect(page).to_have_title("Fixture A, Session 1")
        expect(markdown).to_be_visible()
        markdown.click()
        page.wait_for_function("() => !!window.transcriptFixture.pendingConfig")
        page.wait_for_function("() => window.transcriptFixture.oldPolls.length > 0")
        page.evaluate("window.transcriptFixture.navigate('b')")
        expect(page).to_have_title("Fixture B, Session 2")
        expect(markdown).to_have_attribute("aria-pressed", "false")
        page.evaluate(
            """async () => {
                const f = window.transcriptFixture;
                f.pendingConfig();
                f.oldPolls.splice(0).forEach(release => release());
                // Wait through a frame so both stale promises can settle.
                await new Promise(resolve => requestAnimationFrame(resolve));
            }"""
        )
        accepted.locator("button[aria-expanded]").click()
        expect(accepted).to_contain_text("Session B accepted original text")
        expect(page.get_by_text("Session A accepted original text", exact=False)).to_have_count(0)
        assert page.evaluate("window.transcriptFixture.conversions") == 0

        # Now let the mocked conversion start, then navigate before its reply.
        page.evaluate(
            """() => {
                window.transcriptFixture.mode = 'holdConversion';
                window.transcriptFixture.navigate('a');
            }"""
        )
        expect(page).to_have_title("Fixture A, Session 1")
        markdown.click()
        page.wait_for_function("() => !!window.transcriptFixture.pendingConversion")
        page.evaluate("window.transcriptFixture.navigate('b')")
        expect(page).to_have_title("Fixture B, Session 2")
        page.evaluate(
            """async () => {
                window.transcriptFixture.pendingConversion();
                await new Promise(resolve => requestAnimationFrame(resolve));
            }"""
        )
        expect(markdown).to_have_attribute("aria-pressed", "false")
        accepted.locator("button[aria-expanded]").click()
        expect(accepted).to_contain_text("Session B accepted original text")
        expect(page.get_by_text("STALE CONVERSION MUST NEVER APPEAR")).to_have_count(0)
        recovered = page.locator('[data-transcript-entry="saved-missing-reply"]')
        expect(recovered).to_contain_text("Reconstructed from saved state")
        recovered.locator(".session-transcript-entry-markdown").click()
        expect(recovered).to_contain_text("Session B saved critique")
        # The only conversion was the intentionally mocked A request.
        assert page.evaluate("window.transcriptFixture.conversions") == 1
        browser.close()
    print("PASS provider-free transcript navigation, stale async guards and reconstructed Markdown")


if __name__ == "__main__":
    main()
