"""Render the Assets tab: browse, preview, replace and remove, never game files."""
import os
from pathlib import Path
import struct
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive, make_text_archive
from plugins.ds1 import texts
from plugins.ds1.store import RELATIVE, MARKER
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright

TPF = "chr/c0000/c0000.tpf"
MOVIE = "movww/intro.wmv"


def make_dds(width=16, height=16):
    head = bytearray(128)
    head[0:4] = b"DDS "
    struct.pack_into("<I", head, 4, 124)
    struct.pack_into("<I", head, 8, 0x1 | 0x2 | 0x4 | 0x1000)
    struct.pack_into("<2I", head, 12, height, width)
    struct.pack_into("<I", head, 20, width * 4)
    struct.pack_into("<I", head, 28, 1)
    struct.pack_into("<I", head, 76, 32)
    struct.pack_into("<I", head, 80, 0x41)
    struct.pack_into("<I", head, 88, 32)
    struct.pack_into("<4I", head, 92, 0xFF0000, 0xFF00, 0xFF, 0xFF000000)
    struct.pack_into("<I", head, 108, 0x1000)
    pixels = bytearray()
    for row in range(height):
        for column in range(width):
            pixels += bytes((255 if (row + column) % 2 else 0, 0 if (row + column) % 2 else 255, 128, 255))
    return bytes(head) + bytes(pixels)


def make_tpf(name, width=16, height=16):
    blob = make_dds(width, height)
    encoded = name.encode("shift_jis") + b"\x00"
    head = bytearray(16)
    head[0:4] = b"TPF\x00"
    struct.pack_into("<I", head, 8, 1)
    return bytes(head) + struct.pack("<5I", 16 + 20 + len(encoded), len(blob), 0, 16 + 20, 0) + encoded + blob


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    game_tpf = make_tpf("c0000_diffuse.dds")
    mod_tpf = make_tpf("c0000_custom.dds", 24, 8)
    with tempfile.TemporaryDirectory(prefix="lexeditor-ds1-assets-") as folder:
        temp = Path(folder)
        game, mod = temp / "game", temp / "mod"
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / texts.RELATIVE).parent.mkdir(parents=True)
        (game / texts.RELATIVE).write_bytes(make_text_archive())
        (game / TPF).parent.mkdir(parents=True)
        (game / TPF).write_bytes(game_tpf)
        (game / MOVIE).parent.mkdir(parents=True)
        (game / MOVIE).write_bytes(b"fake movie bytes")
        upload = temp / "replacement.tpf"
        upload.write_bytes(mod_tpf)
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({"LEXEDITOR_DS1_ROOT": str(game), "LEXEDITOR_DS1_PROJECT": str(mod),
                              "LEXEDITOR_NO_MOD": "0", "LEXEDITOR_MOD_READ_ONLY": "0"})
        errors = []
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={"width": 1440, "height": 900})
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    page.locator('[data-tab="assets"]').click()
                    page.wait_for_selector('[data-subtab="overrides"]')
                    page.wait_for_function('state.tab==="assets" && state.sub==="overrides" && !state.error')
                    assert page.locator("[data-subtab]").evaluate_all(
                        "nodes=>nodes.map(n=>n.dataset.subtab)") == ["game", "overrides"]
                    assert page.evaluate("state.rows.length") == 0
                    page.locator('[data-subtab="game"]').click()
                    page.wait_for_function(
                        'state.sub==="game" && state.rows.some(r=>r.id==="chr/c0000/c0000.tpf") && !state.error')
                    page.locator(".lex-list-row", has_text=TPF).click()
                    page.wait_for_function(
                        'state.row?.id==="chr/c0000/c0000.tpf" && state.assetDetail?.source==="game"'
                        ' && state.assetDetail.textures.length===1 && !state.error')
                    preview = page.locator("#main img[alt='c0000_diffuse.dds']")
                    preview.wait_for()
                    assert preview.evaluate("img=>img.naturalWidth") > 0
                    if output:
                        page.screenshot(path=str(output / "assets-game-preview.png"))
                    page.locator(".lex-list-row", has_text=MOVIE).click()
                    page.wait_for_function(
                        'state.row?.id==="movww/intro.wmv" && state.assetDetail?.source==="game"'
                        ' && state.assetDetail.textures.length===0 && !state.error')
                    assert page.locator("#main img").count() == 0
                    page.locator(".lex-list-row", has_text=TPF).click()
                    page.wait_for_function('state.row?.id==="chr/c0000/c0000.tpf" && state.assetDetail?.textures.length===1')
                    # Playwright sets the file behind the hidden picker; the tab
                    # uploads it and lands in Mod files, where it now lives.
                    page.locator('#main input[type="file"]').set_input_files(str(upload))
                    page.wait_for_function(
                        'state.sub==="overrides" && state.rows.some(r=>r.id==="chr/c0000/c0000.tpf")'
                        ' && state.assetDetail?.source==="mod"'
                        ' && state.assetDetail.textures[0].name==="c0000_custom.dds" && !state.assetBusy && !state.error')
                    assert (mod / TPF).read_bytes() == mod_tpf
                    assert page.locator("#main img[alt='c0000_custom.dds']").evaluate("img=>img.naturalWidth") > 0
                    if output:
                        page.screenshot(path=str(output / "assets-override.png"))
                    page.locator('[data-asset-action="remove"]').click()
                    page.locator(".lex-dialog").get_by_role("button", name="Remove").click()
                    page.wait_for_function("state.rows.length===0 && !state.assetBusy && !state.error")
                    assert not (mod / TPF).exists()
                    assert not errors, errors
                finally:
                    browser.close()
            assert (game / TPF).read_bytes() == game_tpf
            assert (game / RELATIVE).read_bytes() == make_archive()
        finally:
            session.stop()
            assert session.wait_closed()
    print("DS1 Assets browse, preview, replace and remove passed.")


if __name__ == "__main__":
    main()
