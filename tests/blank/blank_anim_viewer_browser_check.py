"""Blank proves the shared animation viewer: synthetic frames, no game.

The Animations tab mounts LexeditorUI.animationViewer with a deterministic
2D sample motion. Transport order and shape, shortcuts, and the
context-filtered shortcuts menu are all driven through the real plugin.
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from plugins.blank.plugin import PLUGIN

LABELS = ["Go to animation start", "Back one frame", "Play or pause",
          "Forward one frame", "Go to animation end"]
ANIM_IDS = ["anim-start", "anim-prev", "anim-play", "anim-next", "anim-end"]


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    session = PLUGIN.session_factory()
    errors = []
    session.start()
    try:
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1440, "height": 900})
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(session.url)
                page.wait_for_selector("nav button[data-tab='animations']")
                page.wait_for_function(
                    "document.querySelector('#main').children.length > 0")
                page.locator("nav button[data-tab='animations']").click()
                page.wait_for_selector("[data-blank-anim-host][data-ready='true']",
                                       timeout=30000)
                assert page.evaluate("typeof LexeditorUI.animationViewer") == "function"
                status = page.locator("[data-blank-anim-status]").inner_text()
                assert "Sample motion: 48 frames" in status, status
                assert page.locator("[data-blank-anim-timeline] .lex-anim-marker").count() == 2
                buttons = page.locator("[data-blank-anim-timeline] [data-anim-transport] button")
                assert buttons.count() == 5
                assert [buttons.nth(index).get_attribute("aria-label")
                        for index in range(5)] == LABELS
                for index in range(5):
                    box = buttons.nth(index).bounding_box()
                    assert abs(box["width"] - box["height"]) < 1, (index, box)
                scrub = page.locator("[data-blank-anim-timeline] .lex-anim-scrub").bounding_box()
                bar = page.locator("[data-blank-anim-timeline] [data-anim-transport]").bounding_box()
                assert bar["y"] >= scrub["y"] + scrub["height"] - 1, (scrub, bar)
                readout = lambda: page.locator("[data-blank-anim-timeline] [data-anim-readout]").text_content()
                by_label = {label: buttons.nth(index) for index, label in enumerate(LABELS)}
                by_label["Play or pause"].click()
                by_label["Go to animation end"].click()
                assert readout().startswith("47.0"), readout()
                by_label["Go to animation start"].click()
                assert readout().startswith("0.0"), readout()
                by_label["Forward one frame"].click()
                assert readout().startswith("1.0"), readout()
                by_label["Back one frame"].click()
                assert readout().startswith("0.0"), readout()
                page.evaluate("document.activeElement?.blur()")
                page.keyboard.press("ArrowRight")
                assert readout().startswith("1.0"), readout()
                page.keyboard.press("ArrowLeft")
                assert readout().startswith("0.0"), readout()
                page.keyboard.press("Shift+ArrowRight")
                assert readout().startswith("47.0"), readout()
                page.keyboard.press("Shift+ArrowLeft")
                assert readout().startswith("0.0"), readout()
                playing = lambda: page.evaluate(
                    "document.querySelector('[data-blank-anim-timeline] "
                    "[aria-label=\"Play or pause\"]').textContent")
                paused_glyph = playing()
                page.keyboard.press("Space")
                assert playing() != paused_glyph
                if output:
                    page.wait_for_timeout(300)
                    page.screenshot(path=str(output / "blank-anim-viewer.png"))
                    page.locator("[data-blank-anim-timeline]").screenshot(
                        path=str(output / "blank-anim-transport.png"))
                opener = page.locator("#lexeditor-shortcuts")
                opener.click()
                found = page.locator("[data-lex-shortcut^='anim-']").evaluate_all(
                    "rows => rows.map(row => row.dataset.lexShortcut)")
                assert found == ANIM_IDS, found
                if output:
                    page.screenshot(path=str(output / "blank-shortcuts-in-anim.png"))
                page.keyboard.press("Escape")
                page.locator("nav button[data-tab='organism']").click()
                page.wait_for_selector(".blank-components")
                page.wait_for_timeout(500)
                opener.click()
                assert page.locator('[data-lex-shortcut^="anim-"]').count() == 0
                assert page.locator('[data-lex-shortcut="save"]').count() == 1
                if output:
                    page.screenshot(path=str(output / "blank-shortcuts-outside.png"))
                assert not errors, errors
            finally:
                browser.close()
    finally:
        session.stop()
    print("Blank animation viewer passed.")


if __name__ == "__main__":
    main()
