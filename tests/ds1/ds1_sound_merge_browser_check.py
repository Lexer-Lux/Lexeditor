"""DS1 Sound tab lists streams; banks replace from the stream.

One Sound tab holds SFX and Music subtabs, no Files. SFX and Music list
every stream inside every bank with Bank and Length columns; a stream's
detail names its bank, plays it from a frameless heading button, and
replaces or removes the bank override from its actions.
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
from plugins.ds1.store import RELATIVE, MARKER


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
        temp = Path(temporary)
        game = temp / "game"
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / "sound").mkdir(parents=True)
        (game / "sound" / "sfx_core.fsb").write_bytes(bank_bytes([("hit.wav", 65), ("miss.wav", 2)]))
        (game / "sound" / "frpg_main.fsb").write_bytes(bank_bytes([("boss.wav", 130)]))
        (game / "sound" / "sfx_test.fev").write_bytes(b"not a bank")
        mod = temp / "mod"
        mod.mkdir()
        (mod / MARKER).touch()
        replacement = temp / "replacement.fsb"
        replacement.write_bytes(bank_bytes([("new.wav", 10)]))
        with DS1Session({"LEXEDITOR_DS1_ROOT": str(game),
                         "LEXEDITOR_DS1_PROJECT": str(mod),
                         "LEXEDITOR_NO_MOD": "0"}) as session:
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
                    assert subs.count() == 2, subs.count()
                    assert [subs.nth(index).get_attribute("data-subtab")
                            for index in range(2)] == ["sfx", "music"]
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
                    frame = page.locator(
                        ".lex-detail-panel-heading .lex-detail-panel-icon-audio")
                    assert frame.count() == 1
                    style = frame.evaluate(
                        """n => {const c = getComputedStyle(n);
                           return {border: c.borderStyle, background: c.backgroundColor};}""")
                    assert style == {"border": "none",
                                     "background": "rgba(0, 0, 0, 0)"}, style
                    length = page.evaluate(
                        """[...document.querySelectorAll('.lex-detail-field')]
                           .find(field => field.querySelector('.lex-detail-field-label-text')
                           ?.textContent === 'LENGTH')?.querySelector('input')?.value""")
                    assert length == "1:05", length
                    bank = page.evaluate(
                        """[...document.querySelectorAll('.lex-detail-field')]
                           .find(field => field.querySelector('.lex-detail-field-label-text')
                           ?.textContent === 'BANK')?.querySelector('input')?.value""")
                    assert bank == "sound/sfx_core.fsb", bank
                    actions = page.locator(".lex-detail-section", has_text="ACTIONS").first
                    assert actions.get_by_role("button", name="Replace bank").count() == 1
                    assert actions.get_by_role("button", name="Remove override").count() == 0
                    assert actions.get_by_role("button", name="Show in Files").count() == 0
                    actions.get_by_role("button", name="Replace bank").click()
                    page.locator("#ds1-asset-picker").set_input_files(str(replacement))
                    page.wait_for_function(
                        "() => state.rows.some(row => row.name === 'new.wav' && row.overridden)",
                        timeout=120000)
                    assert (mod / "sound" / "sfx_core.fsb").read_bytes() == replacement.read_bytes()
                    page.wait_for_function(
                        "() => [...document.querySelectorAll('.lex-detail-section')]"
                        ".some(section => section.textContent.includes('Remove override'))",
                        timeout=120000)
                    page.locator(".lex-detail-section", has_text="ACTIONS").first.get_by_role(
                        "button", name="Remove override").click()
                    page.locator(".lex-dialog").get_by_role("button", name="Remove").click()
                    page.wait_for_function(
                        "() => state.rows.some(row => row.name === 'hit.wav' && !row.overridden)",
                        timeout=120000)
                    assert not (mod / "sound" / "sfx_core.fsb").exists()
                    page.evaluate('navigate("sound", "music")')
                    page.wait_for_function(
                        "() => state.sub === 'music' && state.rows.length === 1",
                        timeout=120000)
                finally:
                    browser.close()
    assert not errors, errors
    print("Sound lists SFX and Music streams; banks replace from the stream.")


if __name__ == "__main__":
    main()
