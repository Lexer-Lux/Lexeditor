"""DS1 textures tab: individual textures list, true blanks, scrolling preview.

A multi-texture TPF expands into one row per texture (each naming its
container file), and so does a .chrtpfbdt character archive, one row
per member texture. Single-texture files, split header/data pairs and
unreadable files keep their file rows. Blank detection reads every
pixel: a white texture with one red pixel shows its picture, while a
truly flat one keeps the blank note with no image. The magnifier drawer
scrolls, so a tall texture does not clip.
"""
import struct
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bhf_fixture import make_bhf, make_edge
from bdf_fixture import make_bdf
from ds1_fixture import make_archive, make_text_archive
from plugins.ds1 import texts
from plugins.ds1.store import MARKER, RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright

MULTI = 'chr/c0000/multi.tpf'
SOLO = 'chr/c0000/solo.tpf'
DDS = 'chr/c0000/face.dds'
BHD = 'map/m10/m10.tpfbhd'
BDT = 'map/m10/m10.tpfbdt'
CHR = 'chr/c9999/c9999.chrtpfbdt'


def make_dds(width, height, pixels):
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
    return bytes(head) + bytes(pixels)


def checker_pixels(width, height):
    out = bytearray()
    for row in range(height):
        for column in range(width):
            out += bytes((128, 0 if (row + column) % 2 else 255,
                          255 if (row + column) % 2 else 0, 255))
    return bytes(out)


def solid_pixels(width, height, color=(255, 255, 255, 255)):
    return bytes(color) * (width * height)


def make_tpf(entries):
    """Entries are (name, dds_bytes): one table, packed names, packed blobs."""
    blobs = [dds for _name, dds in entries]
    names = [name.encode('shift_jis') + b'\x00' for name, _dds in entries]
    table = 16 + len(entries) * 20
    name_base = table
    blob_base = name_base + sum(len(encoded) for encoded in names)
    head = bytearray(16)
    head[0:4] = b'TPF\x00'
    struct.pack_into('<I', head, 8, len(entries))
    out = bytes(head)
    offset = blob_base
    name_at = name_base
    for encoded, blob in zip(names, blobs):
        out += struct.pack('<5I', offset, len(blob), 0, name_at, 0)
        offset += len(blob)
        name_at += len(encoded)
    for encoded in names:
        out += encoded
    for blob in blobs:
        out += blob
    return out


def main():
    # 64x64 white with one red pixel at index 1: the old sampler read
    # every 16th pixel and called it blank.
    almost = bytearray(solid_pixels(64, 64))
    almost[4:8] = bytes((0, 0, 255, 255))
    multi = make_tpf([
        ('checker', make_dds(32, 32, checker_pixels(32, 32))),
        ('solid', make_dds(64, 64, solid_pixels(64, 64))),
        ('almost', make_dds(64, 64, bytes(almost))),
        ('tall', make_dds(32, 512, checker_pixels(32, 512))),
    ])
    solo = make_tpf([('lone', make_dds(16, 16, checker_pixels(16, 16)))])
    char = make_bdf([
        make_tpf([('mail_diffuse', make_dds(16, 16, checker_pixels(16, 16)))]),
        make_tpf([('mail_normal', make_dds(16, 16, checker_pixels(16, 16)))]),
    ])
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-tex-tab-') as folder:
        temp = Path(folder)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / texts.RELATIVE).parent.mkdir(parents=True)
        (game / texts.RELATIVE).write_bytes(make_text_archive())
        (game / 'chr' / 'c0000').mkdir(parents=True)
        (game / MULTI).write_bytes(multi)
        (game / SOLO).write_bytes(solo)
        (game / DDS).write_bytes(make_dds(16, 16, checker_pixels(16, 16)))
        (game / 'chr' / 'c9999').mkdir(parents=True)
        (game / CHR).write_bytes(char)
        (game / 'map' / 'm10').mkdir(parents=True)
        edge0 = make_edge(make_tpf([('pair_a', make_dds(16, 16, checker_pixels(16, 16)))]))
        edge1 = make_edge(make_tpf([('pair_b', make_dds(16, 16, checker_pixels(16, 16)))]))
        (game / 'map' / 'm10' / 'm10.tpfbhd').write_bytes(
            make_bhf([('\\tex0', 0, len(edge0)), ('\\tex1', len(edge0), len(edge1))]))
        (game / 'map' / 'm10' / 'm10.tpfbdt').write_bytes(edge0 + edge1)
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
                    page = browser.new_page(viewport={'width': 1400, 'height': 700})
                    page.set_default_timeout(60000)
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=120000)
                    page.locator('[data-tab="textures"]').click()
                    page.wait_for_function(
                        "state.tab==='textures'&&state.rows&&state.rows.length===11")
                    page.wait_for_selector('#main .lex-list-row')
                    kinds = page.evaluate('state.rows.map(r=>`${r.table}:${r.name}`)')
                    for name in ('checker', 'solid', 'almost', 'tall'):
                        assert f'AssetTexture:{name}' in kinds, kinds
                    for name in ('mail_diffuse', 'mail_normal'):
                        assert f'AssetTexture:{name}' in kinds, kinds
                    assert all('.chrtpfbdt' not in name for name in kinds), kinds
                    for name in ('pair_a', 'pair_b'):
                        assert f'AssetTexture:{name}' in kinds, kinds
                    assert f'Asset:{BHD}' not in kinds, kinds
                    assert f'Asset:{SOLO}' in kinds, kinds
                    assert f'Asset:{DDS}' in kinds, kinds
                    assert f'Asset:{BDT}' in kinds, kinds
                    # Each texture row names its container in the File column.
                    files = page.evaluate(
                        'state.rows.filter(r=>r.table==="AssetTexture").map(r=>r.file)')
                    assert files == [MULTI] * 4 + [CHR] * 2 + [BHD] * 2, files
                    row = page.locator('#main .lex-list-row', has_text='almost')
                    assert row.count() == 1
                    assert MULTI in row.inner_text()
                    # Searching the container finds its textures.
                    page.get_by_role('searchbox', name='Search files').fill('multi.tpf')
                    page.wait_for_function('state.rows.length===11')
                    page.wait_for_timeout(300)
                    assert page.locator('#main .lex-list-row', has_text='multi.tpf').count() == 4
                    page.get_by_role('searchbox', name='Search files').fill('')
                    page.wait_for_timeout(300)
                    # No fake blank: one red pixel in white still shows.
                    page.locator('#main .lex-list-row', has_text='almost').click()
                    page.wait_for_selector('.ds1-texture-tile')
                    page.wait_for_function(
                        "document.querySelector('.ds1-texture-tile img')"
                        "?.naturalWidth>0")
                    tile = page.locator('.ds1-texture-tile')
                    assert tile.count() == 1, tile.count()
                    assert 'blank' not in tile.locator('.ds1-texture-name').inner_text()
                    assert tile.locator('img').count() == 1
                    file_value = page.locator(
                        '.lex-detail-field', has_text='FILE').first.locator('input').input_value()
                    assert file_value == MULTI, file_value
                    # The header Add wears the shared header-button look: the
                    # same 28px boxed icon button as every other detail
                    # header, not the inline new-button style.
                    add = page.locator(
                        '.lex-detail-panel-actions button[data-asset-action="add"]')
                    assert add.count() == 1, add.count()
                    assert 'lex-header-icon' in (add.get_attribute('class') or '')
                    assert add.locator('svg').count() == 1
                    box = add.bounding_box()
                    assert (box['width'], box['height']) == (28, 28), box
                    assert page.locator(
                        '.lex-detail-panel-actions .lex-new-button').count() == 0
                    # A character-archive texture previews like any other.
                    page.locator('#main .lex-list-row', has_text='mail_diffuse').click()
                    page.wait_for_selector('.ds1-texture-tile img')
                    page.wait_for_function(
                        "document.querySelector('.ds1-texture-tile img')"
                        "?.naturalWidth>0")
                    # A truly flat texture keeps the blank note, no picture.
                    page.locator('#main .lex-list-row', has_text='solid').click()
                    page.wait_for_function(
                        "document.querySelector('.ds1-texture-tile')"
                        "?.classList.contains('ds1-texture-blank')")
                    blank = page.locator('.ds1-texture-tile')
                    assert blank.count() == 1
                    assert blank.locator('img').count() == 0
                    # The drawer scrolls: the tall texture exceeds it.
                    page.locator('#main .lex-list-row', has_text='tall').click()
                    page.wait_for_selector('.ds1-texture-tile img')
                    page.locator('.lex-detail-panel-heading .lex-model-preview-trigger').click()
                    page.wait_for_selector('.ds1-texture-drawer img')
                    scroll = page.evaluate(
                        """() => { const box = document.querySelector('.ds1-texture-drawer');
                            const style = getComputedStyle(box);
                            return {overflow: style.overflowY,
                                    scrolls: box.scrollHeight > box.clientHeight}; }""")
                    assert scroll['overflow'] in ('auto', 'scroll'), scroll
                    assert scroll['scrolls'], scroll
                    page.locator('.lex-detail-panel-heading .lex-model-preview-trigger').click()
                    # A stale container link lands on its first texture.
                    page.evaluate(f'navigate("textures", "files", "Asset:{MULTI}")')
                    page.wait_for_function(
                        'String(state.selected).startsWith("AssetTexture:")')
                    assert page.evaluate('state.row.file') == MULTI
                    # Split data halves still list as whole files, unpreviewed.
                    archive = page.locator('#main .lex-list-row', has_text=BDT)
                    assert archive.count() == 1
                    assert 'Split archive' in archive.inner_text()
                    assert not errors, f'page errors: {errors[:3]}'
                finally:
                    browser.close()
        finally:
            session.stop()
        print('DS1 textures tab: individual textures, true blanks, scrolling preview passed.')


if __name__ == '__main__':
    main()
