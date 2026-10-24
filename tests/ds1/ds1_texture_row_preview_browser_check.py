"""DS1 textures tab: the pinned icon column previews each file.

Pinning the header preview adds the thumbnail column like any other
pin: every texture file row then carries its first texture as a
loaded icon. Split archives have no per-texture preview, so their
rows keep the word Archive and no icon. A blank texture tile shows
no picture at all, just the name with a blank note.
"""
import struct
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bhf_fixture import make_bhf
from ds1_fixture import make_archive, make_text_archive
from plugins.ds1 import texts
from plugins.ds1.store import MARKER, RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright

TPF = 'chr/c0000/c0000.tpf'
DDS = 'chr/c0000/face.dds'
BLANK = 'chr/c0000/blank.dds'
BHD = 'map/m10/m10.tpfbhd'


def make_dds(width=32, height=32, solid=None):
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
            pixels += bytes(solid) if solid else bytes((255 if (row + column) % 2 else 0,
                                                             0 if (row + column) % 2 else 255, 128, 255))
    return bytes(head) + bytes(pixels)


def make_tpf(name, width=32, height=32):
    blob = make_dds(width, height)
    encoded = name.encode("shift_jis") + b"\x00"
    head = bytearray(16)
    head[0:4] = b"TPF\x00"
    struct.pack_into("<I", head, 8, 1)
    return bytes(head) + struct.pack("<5I", 16 + 20 + len(encoded), len(blob), 0, 16 + 20, 0) + encoded + blob


def main():
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-tex-row-preview-') as folder:
        temp = Path(folder)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / texts.RELATIVE).parent.mkdir(parents=True)
        (game / texts.RELATIVE).write_bytes(make_text_archive())
        (game / 'chr' / 'c0000').mkdir(parents=True)
        (game / TPF).write_bytes(make_tpf('body'))
        (game / DDS).write_bytes(make_dds())
        (game / BLANK).write_bytes(make_dds(16, 16, solid=(255, 255, 255, 255)))
        (game / 'map' / 'm10').mkdir(parents=True)
        (game / 'map' / 'm10' / 'm10.tpfbhd').write_bytes(make_bhf([('/tex0', 0, 8)]))
        (game / 'map' / 'm10' / 'm10.tpfbdt').write_bytes(b'12345678')
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_DS1_PROJECT': str(mod),
                              'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0'})
        errors = []
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1400, 'height': 900})
                    page.set_default_timeout(60000)
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=120000)
                    page.locator('[data-tab="textures"]').click()
                    page.wait_for_function("state.tab==='textures'&&state.rows&&state.rows.length")
                    page.wait_for_selector('#main .lex-list-row')
                    assert page.locator('#main .lex-list-row img').count() == 0, \
                        'no icon column until the preview is pinned'
                    page.locator('#main .lex-list-row').first.click()
                    page.wait_for_function("state.row && !state.error")
                    page.wait_for_timeout(300)
                    page.locator('.lex-detail-panel-icon > .lex-column-pin').click(force=True)
                    page.wait_for_timeout(400)
                    for relative in (TPF, DDS):
                        row = page.locator('#main .lex-list-row', has_text=relative)
                        assert row.count() == 1, f'{relative} listed'
                        icon = row.locator('img.lex-ds1-shop-icon')
                        assert icon.count() == 1, f'{relative} row shows a preview icon'
                        page.wait_for_function(
                            '(relative) => { const row = [...document.querySelectorAll('
                            "'#main .lex-list-row')].find(n => n.textContent.includes(relative));"
                            " const img = row && row.querySelector('img.lex-ds1-shop-icon');"
                            ' return img && img.naturalWidth > 0; }', arg=relative)
                    archive = page.locator('#main .lex-list-row', has_text=BHD)
                    assert archive.count() == 1, 'split archive listed'
                    assert archive.locator('img.lex-ds1-shop-icon').count() == 0, \
                        'split archives have no per-texture preview'
                    assert 'Split archive' in archive.inner_text()
                    page.evaluate(f'navigate("textures", "files", "Asset:{BLANK}")')
                    page.wait_for_selector('.ds1-texture-tile')
                    tile = page.locator('.ds1-texture-tile')
                    page.wait_for_function(
                        "document.querySelector('.ds1-texture-tile').classList.contains"
                        "('ds1-texture-blank')")
                    assert tile.count() == 1, tile.count()
                    assert 'blank' in tile.locator('.ds1-texture-name').inner_text()
                    assert tile.locator('img').count() == 0
                    assert not errors, f'page errors: {errors[:3]}'
                finally:
                    browser.close()
        finally:
            session.stop()
        print('DS1 texture rows: the table previews each file passed.')


if __name__ == '__main__':
    main()
