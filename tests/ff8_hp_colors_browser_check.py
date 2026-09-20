"""Render and exercise the default-off Better HP Colors tweak without saving."""
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from games.ff8.server import create_server
from playwright.sync_api import sync_playwright

server = create_server(0)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        errors = []
        writes = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        def route_api(route):
            if route.request.method != "GET":
                writes.append((route.request.method, route.request.url))
                route.abort()
            else:
                route.continue_()
        page.route("**/api/**", route_api)
        page.goto(f"http://127.0.0.1:{server.server_port}/")
        page.wait_for_function("!document.body.innerText.includes('Preparing Final Fantasy VIII')")
        page.locator('nav [data-tab="settings"]').click()

        field = page.get_by_label("Better HP Colors", exact=True)
        first = page.get_by_role("button", name="First page", exact=True)
        if first.count() and first.is_enabled():
            first.click()
        nxt = page.get_by_role("button", name="Next page", exact=True)
        for _ in range(40):
            if field.count() and field.is_visible():
                break
            if not nxt.count() or not nxt.is_enabled():
                break
            nxt.click()
            page.wait_for_timeout(80)

        field.wait_for()
        assert not field.is_checked(), "Issue #481 must default off"
        text = page.locator("body").inner_text()
        assert "BETTER HP COLORS" in text
        assert "yellow at 50%" in text and "orange at 25%" in text and "KO" in text
        field.check()
        assert field.is_checked()
        field.uncheck()
        assert not field.is_checked()
        assert not writes, writes
        assert not errors, errors
        browser.close()
    print("FF8 Better HP Colors: rendered default-off toggle, semantics and local interaction passed; no writes sent")
finally:
    server.shutdown()
    server.server_close()
    thread.join()
