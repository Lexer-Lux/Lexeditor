"""Frames read as the U+1D453 symbol, never the word.

unitField normalizes the frames/frame unit to the shared symbol, and the
animation scrub readout counts in it.
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

from test_shared_ui_feedback import framework, page  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
SYMBOL = "\U0001d453"


def test_unit_field_renders_frames_as_the_symbol():
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 800, "height": 600})
            page.route("http://fixture/**", lambda r: r.fulfill(body="<html></html>", content_type="text/html"))
            page.goto("http://fixture/")
            css = (ROOT / "ui/framework.css").read_text(encoding="utf-8")
            page.set_content("<style>" + css + "</style><main></main>")
            page.add_script_tag(path=str(ROOT / "ui/framework.js"))
            shown = page.evaluate("""() => {
              const host = document.createElement('div');
              for (const unit of ['frames', 'frame', '%']) {
                const input = document.createElement('input');
                host.append(LexeditorUI.unitField(input, unit));
              }
              document.querySelector('main').append(host);
              return [...host.querySelectorAll('.lex-unit-field')].map(field => [
                field.querySelector('.lex-unit').textContent, field.dataset.lexUnit]);
            }""")
            assert shown == [[SYMBOL, SYMBOL], [SYMBOL, SYMBOL], ["%", "%"]], shown
        finally:
            browser.close()


def test_scrub_readout_counts_frames_in_the_symbol(page):
    from test_anim_viewer import MOUNT, readout
    framework(page)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.evaluate(MOUNT)
    page.wait_for_selector("#anim-host[data-ready='true']")
    text = readout(page)
    assert f"/ 47 {SYMBOL} \u00b7" in text, text
    assert "frames" not in text, text
    assert errors == []
