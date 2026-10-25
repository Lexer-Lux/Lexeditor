"""DS1 Sound tab: one stream's bytes fetch once, not once per render.

The heading player rebuilds on every render, and the stream route
serves no-store bytes, so re-rendering (a search keystroke, a
selection) used to re-download and re-extract the whole stream each
time, serializing the app behind extracts. The first render keeps the
eager play button; the landed bytes swap it for a reused blob URL.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive
from ds1_sound_fixture import bank_bytes
from plugins.ds1.plugin import DS1Session
from plugins.ds1.store import MARKER, RELATIVE
from playwright.sync_api import sync_playwright


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lexeditor-ds1-sound-cache-") as folder:
        temp = Path(folder)
        game, mod = temp / "game", temp / "mod"
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / "sound").mkdir(parents=True)
        (game / "sound" / "sfx_core.fsb").write_bytes(bank_bytes())
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({"LEXEDITOR_DS1_ROOT": str(game),
                              "LEXEDITOR_DS1_PROJECT": str(mod),
                              "LEXEDITOR_NO_MOD": "0"})
        errors = []
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={"width": 1600, "height": 1000})
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    fetches = []
                    page.on("request", lambda request: fetches.append(request.url)
                            if "/api/sound/stream" in request.url else None)
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=120000)
                    page.evaluate('navigate("sound", "sfx", '
                                  '"SoundStream:sound/sfx_core.fsb::o7230.wav")')
                    page.wait_for_function(
                        "() => state.tab === 'sound' && "
                        "document.querySelector('.lex-detail-panel-heading')"
                        "?.textContent?.includes('o7230.wav')",
                        timeout=120000)
                    assert page.locator(
                        ".lex-detail-panel-heading .lex-audio-play").count() == 1
                    # Let the one background fetch land and settle.
                    page.wait_for_timeout(2500)
                    settled = len(fetches)
                    assert settled >= 1, "the stream never fetched"
                    page.evaluate("render(); render(); render()")
                    page.wait_for_timeout(2500)
                    assert len(fetches) == settled, \
                        f"re-renders refetched the stream ({settled} -> {len(fetches)})"
                    assert page.locator(
                        ".lex-detail-panel-heading .lex-audio-play").count() == 1
                    if output:
                        page.screenshot(path=str(output / "sound-cached.png"))
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
    print("DS1 sound stream: fetched once, reused across renders passed.")


if __name__ == "__main__":
    main()
