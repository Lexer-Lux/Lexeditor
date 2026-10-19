"""DS1 Sound tab merges effects and music into flat per-sound lists.

One Sound tab holds SFX, Music and Files subtabs. SFX and Music list
every stream inside every bank with Bank and Length columns; a
stream's detail plays it from the heading and links back to its bank
file. Files keeps the replaceable bank files.
"""
import struct
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "ds1"))
from ds1_fixture import make_archive
from playwright.sync_api import sync_playwright
from plugins.ds1.plugin import DS1Session
from plugins.ds1.store import RELATIVE


def bank_bytes(streams):
    """A header-only FSB4 bank: [(name, seconds)]."""
    data = bytearray(struct.pack("<4sIII", b"FSB4", len(streams), 0, 0) + bytes(32))
    for name, seconds in streams:
        head = bytearray(80)
        struct.pack_into("<H", head, 0, 80)
        encoded = name.encode("ascii")
        head[2:2 + len(encoded)] = encoded
        struct.pack_into("<II", head, 32, seconds * 44100, 1000)
        struct.pack_into("<I", head, 52, 44100)
        data += head
    return bytes(data)


def main():
    errors = []
    with tempfile.TemporaryDirectory(prefix="lexeditor-ds1-sound-merge-") as temporary:
        game = Path(temporary) / "game"
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / "sound").mkdir(parents=True)
        (game / "sound" / "sfx_core.fsb").write_bytes(bank_bytes([("hit.wav", 65), ("miss.wav", 2)]))
        (game / "sound" / "frpg_main.fsb").write_bytes(bank_bytes([("boss.wav", 130)]))
        (game / "sound" / "sfx_test.fev").write_bytes(b"not a bank")
        with DS1Session({"LEXEDITOR_DS1_ROOT": str(game),
                         "LEXEDITOR_NO_MOD": "1"}) as session:
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={"width": 1600, "height": 1000})
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=120000)
                    page.evaluate('navigate("sound")')
                    page.wait_for_function(
                        "() => state.tab === 'sound' && state.sub === 'sfx'",
                        timeout=120000)
                    subs = page.locator(".lex-subtab-bar:not([hidden]) .lex-subtab-button")
                    assert subs.count() == 3, subs.count()
                    assert [subs.nth(index).get_attribute("data-subtab")
                            for index in range(3)] == ["sfx", "music", "files"]
                    assert page.evaluate("state.rows.length") == 2
                    heads = page.locator(".lex-column-list-header .lex-column-list-head-cell")
                    assert "Bank" in heads.nth(1).inner_text()
                    assert "Length" in heads.nth(2).inner_text()
                    page.evaluate('navigate("sound", "sfx", '
                                  '"SoundStream:sound/sfx_core.fsb::hit.wav")')
                    page.wait_for_function(
                        """() => document.querySelector('.lex-detail-panel-heading')
                           ?.textContent?.includes('hit.wav')""",
                        timeout=120000)
                    assert page.locator(
                        ".lex-detail-panel-heading .lex-audio-play").count() == 1
                    length = page.evaluate(
                        """[...document.querySelectorAll('.lex-detail-field')]
                           .find(field => field.querySelector('.lex-detail-field-label-text')
                           ?.textContent === 'LENGTH')?.querySelector('input')?.value""")
                    assert length == "1:05", length
                    page.get_by_role("button", name="Show in Files").click()
                    page.wait_for_function(
                        """() => state.sub === 'files'
                           && state.selected === 'Asset:sound/sfx_core.fsb'""",
                        timeout=120000)
                    page.evaluate('navigate("sound", "music")')
                    page.wait_for_function(
                        "() => state.sub === 'music' && state.rows.length === 1",
                        timeout=120000)
                    page.evaluate('navigate("sound", "files")')
                    page.wait_for_function(
                        "() => state.sub === 'files' && state.rows.length === 3",
                        timeout=120000)
                finally:
                    browser.close()
    assert not errors, errors
    print("Sound merges SFX, Music and Files; streams play and link to their banks.")


if __name__ == "__main__":
    main()
