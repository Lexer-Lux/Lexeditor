"""A Play-sound event's Sound is a hoverable plus a thing finder.

The Sound number keeps its input and gains the derived stream's face
beside it: hover previews the bank's stream with a player, clicking
opens it in the Sound tab, and the finder holds-to-choose another
numbered stream while the event's own bank selector stays untouched.
Streams without a number are never candidates. Synthetic binders only.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "ds1"))
from ds1_fixture import make_archive
from flver_fixture import build_flver, make_chrbnd
from hkx_fixture import build_tag0
from tae_fixture import build_anibnd, build_tae
from test_ds1_sound_bank import bank_bytes
from plugins.ds1.store import RELATIVE, MARKER
from plugins.ds1.tae_store import CHR_DIR
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright

BINDER = "c1200.anibnd.dcx"
TAE = "a87.tae"


def drill_to_events(page, events=4):
    page.locator('[data-tab="animations"]').click()
    page.wait_for_function("state.tab==='animations' && state.animChars.length===1")
    # Re-entry lands on the previous left tab; the drill starts at characters.
    page.locator('[data-anim-left] [data-tabstrip-id="chars"]').click()
    page.locator("[data-anim-chars] .lex-list-row", has_text="c1200").click()
    page.locator('[data-anim-left] [data-tabstrip-id="anims"]').click()
    page.wait_for_function("state.animScope.level==='anims' && state.rows.length===2")
    page.locator("[data-anim-list] .lex-list-row", has_text="a87_3300.HKX").click()
    page.locator('[data-anim-left] [data-tabstrip-id="events"]').click()
    page.wait_for_function(f"state.animScope.level==='events' && state.rows.length==={events}")


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    errors = []
    with tempfile.TemporaryDirectory(prefix="lexeditor-ds1-anim-sound-") as temp:
        game, mod = Path(temp) / "game", Path(temp) / "mod"
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / CHR_DIR).mkdir(parents=True)
        (game / CHR_DIR / BINDER).write_bytes(build_anibnd({
            "Skeleton.hkx": build_tag0(), "a87_3300.hkx": build_tag0(), TAE: build_tae()}))
        (game / CHR_DIR / "c1200.chrbnd.dcx").write_bytes(make_chrbnd(build_flver()))
        (game / "sound").mkdir(parents=True)
        (game / "sound" / "frpg_se0.fsb").write_bytes(
            bank_bytes(("o7230.wav", "o7250.wav", "silen.wav")))
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({"LEXEDITOR_DS1_ROOT": str(game), "LEXEDITOR_DS1_PROJECT": str(mod),
                              "LEXEDITOR_NO_MOD": "0", "LEXEDITOR_MOD_READ_ONLY": "0"})
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={"width": 1440, "height": 900})
                    page.on("pageerror", lambda e: errors.append(str(e)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    drill_to_events(page)
                    # A new Play-sound event starts unresolved: no bank
                    # holds stream 0.
                    page.locator('[data-tae-action="add"]').click()
                    page.wait_for_selector('[data-tae-input="type"]')
                    page.locator('[data-tae-input="type"]').select_option("128")
                    page.locator('[data-tae-input="start"]').fill("0.1")
                    page.locator('[data-tae-input="end"]').fill("0.2")
                    page.get_by_role("button", name="Create event", exact=True).click()
                    page.wait_for_function("state.rows.length===5 && state.row?.type===128")
                    detail = page.locator("[data-anim-detail]")
                    assert detail.locator(
                        ".ds1-sound-face .ds1-unset-face").inner_text() == "Unknown sound 0"
                    # Typing a held number grows the hoverable face.
                    number = detail.locator('input[data-field-key="soundId"]')
                    number.fill("7230")
                    number.press("Tab")
                    page.wait_for_function(
                        "state.pending===0 && state.row.fields.find(f=>f.key==='soundId').value===7230")
                    face = detail.locator(".ds1-sound-face .lex-hoverable")
                    assert face.inner_text() == "o7230.wav"
                    assert face.get_attribute("data-hover-target-type") == "ds1-sound"
                    # Hover previews the derived bank's stream with a player.
                    face.hover()
                    card = page.locator(".lex-help-popover")
                    card.wait_for()
                    assert "o7230.wav" in card.inner_text()
                    assert "sound/frpg_se0.fsb" in card.inner_text()
                    src = card.locator("audio").get_attribute("src")
                    assert "stream=o7230.wav" in src, src
                    if output:
                        page.screenshot(path=str(output / "anim-sound-preview.png"))
                    # Clicking opens the stream in the Sound tab.
                    face.click()
                    page.wait_for_function("state.tab==='sound' && state.sub==='sfx'")
                    assert page.evaluate("state.selected") == \
                        "SoundStream:sound/frpg_se0.fsb::o7230.wav"
                    assert "o7230.wav" in page.locator(".lex-detail-panel-title").inner_text()
                    # The finder holds-to-choose another numbered stream.
                    drill_to_events(page, 5)
                    page.locator("[data-anim-list] .lex-list-row", has_text="0.10s").click()
                    page.wait_for_function("state.row?.type===128")
                    page.locator('[aria-label="Change Sound"]').click()
                    page.locator(".lex-searcher-bar").wait_for()
                    assert page.locator(".lex-searcher-prompt").inner_text().startswith(
                        "Choose the sound for ")
                    page.wait_for_function(
                        "document.querySelectorAll('.lex-search-candidate').length >= 2")
                    rows = page.locator(".lex-list-row", has_text="silen.wav")
                    assert rows.count() >= 1
                    assert rows.first.evaluate("n=>!n.classList.contains('lex-search-candidate')")
                    box = page.locator(
                        '.lex-search-candidate', has_text="o7250.wav").bounding_box()
                    page.mouse.move(box["x"] + 40, box["y"] + box["height"] / 2)
                    page.mouse.down()
                    page.wait_for_function(
                        'document.querySelector(".lex-searcher-bar") === null', timeout=10000)
                    page.wait_for_function(
                        "state.tab==='animations' && state.row?.type===128 && state.pending===0")
                    title = detail.locator(".lex-detail-panel-title").bounding_box()
                    page.mouse.move(title["x"] + title["width"] / 2, title["y"] + title["height"] / 2)
                    page.mouse.up()
                    page.wait_for_function(
                        "state.row.fields.find(f=>f.key==='soundId').value===7250")
                    assert detail.locator(
                        ".ds1-sound-face .lex-hoverable").inner_text() == "o7250.wav"
                    # The pick stores the number; the bank selector is untouched.
                    assert page.evaluate(
                        "state.row.fields.find(f=>f.key==='soundType').value") == 0
                    if output:
                        page.screenshot(path=str(output / "anim-sound-detail.png"))
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
    print("DS1 animation play-sound face and finder passed.")


if __name__ == "__main__":
    main()
