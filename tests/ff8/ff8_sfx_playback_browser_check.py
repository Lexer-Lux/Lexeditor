"""The SFX tab plays from its header and from every table row.

The detail header carries the play button and its scrubber; the table's
first column holds one play button per valid sound (an em dash where a
sound has no audio). One sound plays at a time: starting a second row
stops the first.
"""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from playwright.sync_api import sync_playwright
from plugins.ff8.plugin import FF8Session


def label(page, key):
    return page.evaluate(f"""() => document.querySelector(
      '.lex-column-list-row[data-key="{key}"] .lex-audio-play')
      ?.getAttribute('aria-label') || "" """)


def wait_label(page, key, word):
    page.wait_for_function(f"""() => document.querySelector(
      '.lex-column-list-row[data-key="{key}"] .lex-audio-play')
      ?.getAttribute('aria-label')?.startsWith('{word}')""", timeout=15000)


def main():
    with tempfile.TemporaryDirectory(prefix="lexeditor-sfx-playback-") as project:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project}) as session, sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True,
                                         args=["--autoplay-policy=no-user-gesture-required"])
            page = browser.new_page(viewport={"width": 1600, "height": 1000})
            page.goto(session.url)
            page.wait_for_function("typeof state!=='undefined'&&!state.booting", timeout=90000)
            page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')", timeout=30000)
            page.evaluate("state.selected.sfx=1;navigate('sfx')")
            page.wait_for_selector(".lex-detail-panel-heading .lex-audio-play", timeout=120000)
            assert page.locator(".lex-detail-panel-heading .lex-audio-scrub").count() == 1
            assert page.locator('.lex-column-list-row[data-key="0"] .lex-audio-play').count() == 0
            assert "Play" in label(page, 1)
            page.locator('.lex-column-list-row[data-key="1"] .lex-audio-play').click()
            wait_label(page, 1, "Pause")
            page.locator('.lex-column-list-row[data-key="2"] .lex-audio-play').click()
            wait_label(page, 2, "Pause")
            assert label(page, 1).startswith("Play"), label(page, 1)
            page.locator('.lex-column-list-row[data-key="2"] .lex-audio-play').click()
            wait_label(page, 2, "Play")
            browser.close()
            print("SFX plays from its header and every table row, one sound at a time.")


if __name__ == "__main__":
    main()
