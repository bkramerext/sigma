"""Real-Chrome Home credit effects: delayed dual-line streak and click action."""

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
    page.goto(os.environ.get("SIGMA_BROWSER_BASE_URL", "http://127.0.0.1:5173/"))
    credit = page.locator(".home-art-credit")
    expect(credit).to_be_visible()
    name_line = credit.locator(":scope > span").first
    models_line = credit.locator(":scope > span").nth(1)
    name_box = name_line.bounding_box()
    models_box = models_line.bounding_box()
    assert name_box and models_box

    page.mouse.move(name_box["x"] + name_box["width"] / 2, name_box["y"] + name_box["height"] / 2)
    streak = page.locator(".home-credit-streak")
    expect(streak).to_have_count(2)
    name_streak = page.locator(".home-credit-streak--name")
    models_streak = page.locator(".home-credit-streak--models")
    start = name_streak.evaluate("e => e.getAnimations()[0].currentTime")
    page.wait_for_timeout(120)
    page.mouse.move(models_box["x"] + models_box["width"] / 2, models_box["y"] + models_box["height"] / 2)
    page.wait_for_timeout(90)
    moving = name_streak.evaluate("e => e.getAnimations()[0].currentTime")
    assert moving > start + 70, (start, moving)
    name_streak_box = name_streak.bounding_box()
    models_streak_box = models_streak.bounding_box()
    assert name_streak_box and models_streak_box and -120 < name_streak_box["x"] < 1440
    assert abs(name_streak_box["y"] + .5 - (name_box["y"] + name_box["height"] / 2)) <= 1
    assert abs(models_streak_box["y"] + models_streak_box["height"] / 2 - (models_box["y"] + models_box["height"] / 2)) <= 1, (models_streak_box, models_box)
    assert models_streak.evaluate("e => e.getAnimations()[0].effect.getTiming().delay") == 200

    page.mouse.move(20, 20)
    page.wait_for_timeout(100)
    expect(streak).to_have_count(2)
    page.wait_for_function("!document.querySelector('.home-credit-streak')", timeout=2000)

    page.mouse.move(name_box["x"] + name_box["width"] / 2, name_box["y"] + name_box["height"] / 2)
    expect(streak).to_have_count(2)
    page.mouse.click(name_box["x"] + name_box["width"] / 2, name_box["y"] + name_box["height"] / 2)
    expect(credit.locator(".home-credit-plunk")).to_have_count(1)
    expect(page.locator(".home-shell")).to_have_class("home-shell home-credit-plunk-active")
    page.wait_for_function("!document.querySelector('.home-credit-streak')", timeout=2000)

    for width, height in ((1440, 900), (390, 844)):
        page.set_viewport_size({"width": width, "height": height})
        credit = page.locator(".home-art-credit")
        name_line = credit.locator(":scope > span").first
        models_line = credit.locator(":scope > span").nth(1)
        name_box = name_line.bounding_box()
        models_box = models_line.bounding_box()
        assert name_box and models_box
        page.mouse.move(20, 20)
        page.mouse.move(name_box["x"] + name_box["width"] / 2, name_box["y"] + name_box["height"] / 2)
        expect(streak).to_have_count(2)
        page.wait_for_timeout(220)
        models_streak_box = models_streak.bounding_box()
        assert models_streak_box
        assert abs(models_streak_box["y"] + models_streak_box["height"] / 2 - (models_box["y"] + models_box["height"] / 2)) <= 1, (width, models_streak_box, models_box)
        page.screenshot(path=f"/tmp/sigma-home-effects-{width}.png", full_page=True)
        page.wait_for_function("!document.querySelector('.home-credit-streak')", timeout=2000)

    browser.close()
print("PASS real-Chrome credit hover runs delayed, line-aligned streaks once per hover on desktop and mobile; credit click action remains active")
