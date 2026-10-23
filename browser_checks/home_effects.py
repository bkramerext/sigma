"""Real-Chrome Home credit effects: one-shot streak and click shimmer."""

import os

from playwright.sync_api import expect, sync_playwright


with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=os.environ.get(
            "SIGMA_BROWSER_EXECUTABLE",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        headless=True,
    )
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.emulate_media(reduced_motion="no-preference")
    page.goto("http://127.0.0.1:5173/")
    credit = page.locator(".home-art-credit")
    expect(credit).to_be_visible()
    name_line = credit.locator(":scope > span").first
    name_box = name_line.bounding_box()
    date_box = credit.locator("time").bounding_box()
    assert name_box and date_box

    page.mouse.move(name_box["x"] + name_box["width"] / 2, name_box["y"] + name_box["height"] / 2)
    streak = page.locator(".home-credit-streak")
    expect(streak).to_have_count(1)
    start = streak.evaluate("e => e.getAnimations()[0].currentTime")
    page.wait_for_timeout(120)
    page.mouse.move(date_box["x"] + date_box["width"] / 2, date_box["y"] + date_box["height"] / 2)
    page.wait_for_timeout(90)
    moving = streak.evaluate("e => e.getAnimations()[0].currentTime")
    assert moving > start + 70, (start, moving)
    streak_box = streak.bounding_box()
    assert streak_box and -120 < streak_box["x"] < 0
    assert name_box["y"] <= streak_box["y"] + 1 <= name_box["y"] + name_box["height"]

    page.mouse.move(20, 20)
    page.wait_for_timeout(100)
    expect(streak).to_have_count(1)
    page.wait_for_function("!document.querySelector('.home-credit-streak')", timeout=2000)

    page.mouse.move(name_box["x"] + name_box["width"] / 2, name_box["y"] + name_box["height"] / 2)
    expect(streak).to_have_count(1)
    page.mouse.click(name_box["x"] + name_box["width"] / 2, name_box["y"] + name_box["height"] / 2)
    shimmer = page.locator(".home-credit-shimmer")
    expect(shimmer).to_have_count(1)
    shimmer_box = shimmer.bounding_box()
    assert shimmer_box and shimmer_box["x"] > 1440 / 2
    page.wait_for_function("!document.querySelector('.home-credit-shimmer')", timeout=2000)

    for width, height in ((1440, 900), (390, 844)):
        page.set_viewport_size({"width": width, "height": height})
        credit = page.locator(".home-art-credit")
        name_line = credit.locator(":scope > span").first
        name_box = name_line.bounding_box()
        assert name_box
        page.mouse.move(name_box["x"] + name_box["width"] / 2, name_box["y"] + name_box["height"] / 2)
        expect(streak).to_have_count(1)
        page.screenshot(path=f"/tmp/sigma-home-effects-{width}.png", full_page=True)
        page.wait_for_function("!document.querySelector('.home-credit-streak')", timeout=2000)

    browser.close()
print("PASS real-Chrome credit hover runs one uninterrupted streak; rehover and click trigger new streak and right-art shimmer on desktop and mobile")
