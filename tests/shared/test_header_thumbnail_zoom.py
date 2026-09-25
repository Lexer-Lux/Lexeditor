"""Header thumbnails expand on hover, except model-viewer triggers.

A details-panel header thumbnail that does not open the model viewer shows a
floating enlargement on hover so the art can be previewed at a readable size.
A thumbnail that opens the model viewer keeps its magnifier instead.
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
ICON = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
        "AAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")


def _page(play):
    browser = play.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1100, "height": 800})
    page.route("http://fixture/**", lambda r: r.fulfill(
        body="<main></main>", content_type="text/html"))
    page.goto("http://fixture/")
    page.add_style_tag(path=str(ROOT / "ui/framework.css"))
    page.add_script_tag(path=str(ROOT / "ui/framework.js"))
    return browser, page


def test_plain_header_thumbnail_expands_on_hover():
    with sync_playwright() as play:
        browser, page = _page(play)
        try:
            page.evaluate("""(iconURL) => {
              const icon = document.createElement('img');
              icon.src = iconURL;
              icon.alt = '';
              const panel = LexeditorUI.detailPanel({title: 'Example', icon, body: 'Fields'});
              document.querySelector('main').append(panel);
            }""", ICON)
            icon = page.locator(".lex-detail-panel-icon")
            assert icon.count() == 1
            assert page.locator(".lex-header-thumb-zoom").count() == 0
            icon.hover()
            page.wait_for_selector(".lex-header-thumb-zoom", timeout=2000)
            zoom = page.locator(".lex-header-thumb-zoom")
            assert zoom.evaluate("n=>getComputedStyle(n).pointerEvents") == "none"
            assert zoom.get_attribute("aria-hidden") == "true"
            box = zoom.evaluate("""n => { const r = n.getBoundingClientRect();
              return {left: r.left, top: r.top, right: r.right, bottom: r.bottom}; }""")
            assert box["left"] >= 0 and box["top"] >= 0
            assert box["right"] <= 1100 and box["bottom"] <= 800
            assert zoom.locator("img").count() == 1
            page.mouse.move(5, 5)
            page.wait_for_timeout(200)
            assert page.locator(".lex-header-thumb-zoom").count() == 0
        finally:
            browser.close()


def test_model_preview_trigger_does_not_expand_on_hover():
    with sync_playwright() as play:
        browser, page = _page(play)
        try:
            page.evaluate("""(iconURL) => {
              const icon = document.createElement('img');
              icon.src = iconURL;
              icon.alt = '';
              const panel = LexeditorUI.detailPanel({title: 'Example', icon, body: 'Fields'});
              LexeditorUI.attachModelPreview(panel, {
                content: () => LexeditorUI.modelStage({message: 'Model fixture'}),
              });
              document.querySelector('main').append(panel);
            }""", ICON)
            trigger = page.get_by_role("button", name="Open model preview", exact=True)
            assert trigger.count() == 1
            trigger.hover()
            page.wait_for_timeout(300)
            assert page.locator(".lex-header-thumb-zoom").count() == 0
        finally:
            browser.close()
