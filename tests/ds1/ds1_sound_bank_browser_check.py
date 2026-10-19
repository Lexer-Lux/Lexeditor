"""DS1 sound banks play from the detail header and every stream row.

A bank's detail lists its streams with Length and Size, one play button
per row; the header plays the selected stream with its scrubber. One
sound plays at a time. Non-bank sound files keep the honest No preview
note and no player.
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


def bank_bytes(names=("o7230.wav", "silen.wav")):
    """An FSB4 bank with framed MPEG payloads, one stream per name."""
    frame = bytes.fromhex("fffba060") + bytes(522 - 4)
    primer = bytes.fromhex("0a00fffb") + bytes(12)
    payloads = [primer + frame + b"\0\0" + frame for _ in names]
    data = bytearray(struct.pack("<4sIII", b"FSB4", len(names), 0, 0) + bytes(32))
    for name, payload in zip(names, payloads):
        head = bytearray(80)
        struct.pack_into("<H", head, 0, 80)
        encoded = name.encode("ascii")
        head[2:2 + len(encoded)] = encoded
        struct.pack_into("<II", head, 32, 2304, len(payload))
        struct.pack_into("<I", head, 52, 44100)
        data += head
    for payload in payloads:
        data += payload
    return bytes(data)


def main():
    errors = []
    with tempfile.TemporaryDirectory(prefix="lexeditor-ds1-sound-bank-") as temporary:
        game = Path(temporary) / "game"
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / "sound").mkdir(parents=True)
        (game / "sound" / "frpg_main.fsb").write_bytes(bank_bytes())
        (game / "sound" / "sfx_test.fev").write_bytes(b"not a bank")
        with DS1Session({"LEXEDITOR_DS1_ROOT": str(game),
                         "LEXEDITOR_NO_MOD": "1"}) as session:
            with sync_playwright() as play:
                browser = play.chromium.launch(
                    headless=True, args=["--autoplay-policy=no-user-gesture-required"])
                try:
                    page = browser.new_page(viewport={"width": 1600, "height": 1000})
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=120000)
                    page.evaluate('navigate("sound", "files", "Asset:sound/frpg_main.fsb")')
                    page.wait_for_selector(".lex-detail-section .lex-audio-play", timeout=120000)
                    rows = page.locator(".lex-detail-section .lex-column-list-row[data-key]")
                    assert rows.count() == 2, rows.count()
                    assert "o7230.wav" in rows.nth(0).inner_text()
                    assert page.locator(
                        ".lex-detail-panel-heading .lex-audio-play").count() == 1
                    assert page.locator(
                        ".lex-detail-panel-heading .lex-audio-scrub").count() == 1
                    page.locator('.lex-detail-section .lex-column-list-row[data-key="silen.wav"] '
                                 ".lex-audio-play").click()
                    page.wait_for_function(
                        """() => document.querySelector('.lex-detail-section .lex-column-list-row[data-key="silen.wav"] .lex-audio-play')
                           ?.getAttribute('aria-label')?.startsWith('Pause')""", timeout=15000)
                    page.locator(".lex-detail-panel-heading .lex-audio-play").click()
                    page.wait_for_function(
                        """() => document.querySelector('.lex-detail-panel-heading .lex-audio-play')
                           ?.getAttribute('aria-label')?.startsWith('Pause')""", timeout=15000)
                    assert page.evaluate(
                        """document.querySelector('.lex-detail-section .lex-column-list-row[data-key="silen.wav"] .lex-audio-play')
                           ?.getAttribute('aria-label')?.startsWith('Play')""") is True
                    page.evaluate('navigate("sound", "files", "Asset:sound/sfx_test.fev")')
                    page.wait_for_function(
                        """() => (state.tab === 'sound' && state.selected === 'Asset:sound/sfx_test.fev'
                           && document.querySelector('.lex-detail-panel .lex-detail-field-control input')?.value === 'No preview')""",
                        timeout=120000)
                    assert page.locator(".lex-detail-panel .lex-audio-play").count() == 0
                finally:
                    browser.close()
    assert not errors, errors
    print("Bank streams play from the header and every row; project files keep No preview.")


if __name__ == "__main__":
    main()
