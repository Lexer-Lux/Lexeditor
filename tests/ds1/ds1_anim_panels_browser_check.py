"""Animations panes: per-panel pagination without scrollbars, textures, bones.

Each side panel pages its own list with a compact pager that lives
inside the panel (never the window's fixed bottom bar), shows only
rows that fit (paginated lists never scroll), turns pages with the
mouse wheel, and both pagers work. The compact pager shows no
X-Y/Z position count.
The viewer binds the model's diffuse textures, and bones parented
under a model-only SFX anchor still follow the Havok hierarchy.
Synthetic fixtures only; read-only with no mod.
"""
import io
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive
from flver_fixture import build_flver, make_chrbnd
from hkx_fixture import build_tag0
from tae_fixture import build_anibnd, build_tae
from tpf_fixture import make_dds_rgba, make_tpf
from plugins.ds1.store import RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright

NCHARS = 25
NMOTIONS = 25

# An SFX anchor between root and child in the model only: model
# worlds still match the Havok rig (root (0,1,0), child (0,1,1)).
SFX_BONES = [
    ('root', -1, (0.0, 1.0, 0.0), (0.0, 0.0, 0.0), (1.0, 1.0, 1.0)),
    ('sfx', 0, (0.0, 9.0, 0.0), (0.0, 0.0, 0.0), (1.0, 1.0, 1.0)),
    ('child', 1, (0.0, -9.0, 1.0), (0.0, 0.0, 0.0), (1.0, 1.0, 1.0)),
]
SFX_SKIN = [((2, 2, 2, 2), (1.0, 0.0, 0.0, 0.0))] * 4


def close_enough(found, want, tol=0.05):
    assert len(found) == len(want), (found, want)
    for left, right in zip(found, want):
        assert abs(left - right) <= tol, (found, want)


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-anim-panels-') as folder:
        temp = Path(folder)
        game = temp / 'game'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / 'chr').mkdir(parents=True)
        tag = build_tag0()
        red = make_dds_rgba(4, 4, [(255, 0, 0, 255)] * 16)
        tpf = make_tpf([('tex0', red)])
        for n in range(NCHARS):
            cid = f'c12{n:02d}'
            members = {'Skeleton.hkx': tag, 'a87.tae': build_tae()}
            for m in range(NMOTIONS):
                members[f'a87_{3300 + m}.hkx'] = tag
            (game / 'chr' / f'{cid}.anibnd.dcx').write_bytes(build_anibnd(members))
            if cid == 'c1200':
                flver = build_flver(bones=SFX_BONES, skin=SFX_SKIN, pos_offset=(0.0, 1.0, 1.0))
            else:
                flver = build_flver()
            (game / 'chr' / f'{cid}.chrbnd.dcx').write_bytes(
                make_chrbnd(flver, cid, [(f'{cid}.tpf', tpf)]))
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_NO_MOD': '1',
                              'LEXEDITOR_MOD_READ_ONLY': '1'})
        errors = []
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    page.locator('button[data-tab="animations"]').click()
                    page.wait_for_function('state.tab === "animations" && !state.error')
                    page.wait_for_selector('[data-anim-host]')
                    page.wait_for_selector("[data-anim-host][data-ready='true']", timeout=30000)
                    page.wait_for_timeout(500)
                    assert page.locator('.ds1-anim .lex-collapsible-handle').count() == 0
                    widths = page.evaluate(
                        """() => [document.querySelector('[data-anim-left-panel]')
                            .getBoundingClientRect().width,
                          document.querySelector('[data-anim-detail-panel]')
                            .getBoundingClientRect().width]""")
                    assert [round(width) for width in widths] == [360, 360], widths
                    for pane in ('[data-anim-chars]', '[data-anim-list]'):
                        if pane == '[data-anim-list]':
                            page.locator('[data-anim-left] [data-tabstrip-id="anims"]').click()
                        assert page.locator(f'{pane} .lex-pager').count() == 1, pane
                        assert page.locator(f'{pane} .lex-pager.lex-pager-inline').count() == 1, pane
                        box = page.evaluate(
                            """(pane) => {
                                const panel = document.querySelector(pane).getBoundingClientRect();
                                const bar = document.querySelector(pane + ' .lex-pager').getBoundingClientRect();
                                const list = document.querySelector(pane + ' .lex-column-list');
                                return {inside: bar.top >= panel.top - 1 && bar.bottom <= panel.bottom + 1
                                            && bar.left >= panel.left - 1 && bar.right <= panel.right + 1,
                                        scrollable: list.scrollHeight > list.clientHeight + 1};
                            }""", pane)
                        assert box['inside'], (pane, 'pager escapes its panel')
                        assert not box['scrollable'], (pane, 'paginated list scrolls')
                        gap = page.evaluate(
                            """(pane) => {
                                const rows = [...document.querySelectorAll(
                                    pane + ' .lex-column-list-row')];
                                const bar = document.querySelector(pane + ' .lex-pager')
                                    .getBoundingClientRect();
                                const last = rows[rows.length - 1].getBoundingClientRect();
                                return bar.top - last.bottom;
                            }""", pane)
                        assert gap < 6, (pane, gap)
                    assert page.locator('.ds1-anim .lex-pager:not(.lex-pager-inline)').count() == 0
                    page.locator('[data-anim-left] [data-tabstrip-id="chars"]').click()
                    assert page.locator('[data-anim-chars] .lex-compact-pager').count() == 1
                    assert page.locator('[data-anim-chars] .lex-page-summary').count() == 0
                    page.locator('[data-anim-left] [data-tabstrip-id="anims"]').click()
                    assert page.locator('[data-anim-list] .lex-compact-pager').count() == 1
                    assert page.locator('[data-anim-list] .lex-page-summary').count() == 0
                    page.locator('[data-anim-left] [data-tabstrip-id="chars"]').click()
                    first_chars = page.locator('[data-anim-chars] .lex-list-row').first.inner_text()
                    page.locator("[data-anim-chars] .lex-pager button[aria-label='Next page']").click()
                    page.wait_for_function('state.animCharPage === 1')
                    assert page.locator('[data-anim-chars] .lex-list-row').first.inner_text() != first_chars
                    page.locator("[data-anim-chars] .lex-pager button[aria-label='First page']").click()
                    page.wait_for_function('state.animCharPage === 0')
                    box = page.locator('[data-anim-chars] .lex-column-list').bounding_box()
                    page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
                    page.mouse.wheel(0, 120)
                    page.wait_for_function('state.animCharPage === 1')
                    page.wait_for_timeout(250)
                    page.mouse.wheel(0, -120)
                    page.wait_for_function('state.animCharPage === 0')
                    page.locator('[data-anim-left] [data-tabstrip-id="anims"]').click()
                    first_motions = page.locator('[data-anim-list] .lex-list-row').first.inner_text()
                    page.locator("[data-anim-list] .lex-pager button[aria-label='Next page']").click()
                    page.wait_for_function('state.animPage === 1')
                    assert page.locator('[data-anim-list] .lex-list-row').first.inner_text() != first_motions
                    page.locator("[data-anim-list] .lex-pager button[aria-label='First page']").click()
                    page.wait_for_function('state.animPage === 0')
                    box = page.locator('[data-anim-list] .lex-column-list').bounding_box()
                    page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
                    page.mouse.wheel(0, 120)
                    page.wait_for_function('state.animPage === 1')
                    page.wait_for_timeout(250)
                    page.mouse.wheel(0, -120)
                    page.wait_for_function('state.animPage === 0')
                    # Textures: the plain quad renders in its diffuse red.
                    page.locator('[data-anim-left] [data-tabstrip-id="chars"]').click()
                    page.locator('[data-anim-chars] .lex-list-row', has_text='c1201').click()
                    page.wait_for_function(
                        '!document.querySelector("[data-anim-host]").hasAttribute("data-ready")',
                        timeout=30000)
                    page.wait_for_selector("[data-anim-host][data-ready='true']", timeout=30000)
                    shot = page.locator('canvas[data-viewport]').screenshot()
                    pixels = Image.open(io.BytesIO(shot)).convert('RGB')
                    colors = pixels.getcolors(maxcolors=1 << 20) or []
                    total = sum(count for count, _ in colors)
                    reds = sum(count for count, (red, green, blue) in colors
                               if red > 150 and green < 110 and blue < 110)
                    assert total and reds / total > 0.05, (reds, total)
                    if output:
                        page.screenshot(path=str(output / 'anim-panels.png'))
                    # Bones: the child follows its Havok parent, skipping the
                    # model-only SFX anchor (frame 0, paused). The fixture's
                    # root reference scale is 2, doubling child offsets.
                    page.locator('[data-anim-chars] .lex-list-row', has_text='c1200').click()
                    page.wait_for_function(
                        '!document.querySelector("[data-anim-host]").hasAttribute("data-ready")',
                        timeout=30000)
                    page.wait_for_selector("[data-anim-host][data-ready='true']", timeout=30000)
                    page.locator('[data-anim-timeline] button[aria-label="Play or pause"]').click()
                    page.locator('[data-anim-timeline] input[type="range"]').fill('0')
                    page.wait_for_function(
                        'document.querySelector("[data-anim-readout]")?.textContent?.startsWith("0.0")',
                        timeout=10000)
                    page.wait_for_timeout(300)
                    bones = page.evaluate(
                        "document.querySelector('[data-anim-host]')._animBones()")
                    by_name = {bone['name']: bone['pos'] for bone in bones}
                    assert sorted(by_name) == ['child', 'root', 'sfx'], sorted(by_name)
                    root = by_name['root']
                    close_enough(root, (0.0, 1.0, 0.0))
                    close_enough([by_name['child'][axis] - root[axis] for axis in range(3)],
                                 (0.0, 10.0, 12.0))
                    close_enough([by_name['sfx'][axis] - root[axis] for axis in range(3)],
                                 (0.0, 18.0, 0.0))
                    for pane, last in (('[data-anim-chars]', "[data-anim-chars] .lex-pager"
                                              " button[aria-label='Last page']"),
                                       ('[data-anim-list]', "[data-anim-list] .lex-pager"
                                             " button[aria-label='Last page']")):
                        tab = 'chars' if pane == '[data-anim-chars]' else 'anims'
                        page.locator(f'[data-anim-left] [data-tabstrip-id="{tab}"]').click()
                        page.locator(last).click()
                        page.wait_for_timeout(400)
                        gap = page.evaluate(
                            """(pane) => {
                                const rows = [...document.querySelectorAll(
                                    pane + ' .lex-column-list-row')];
                                const bar = document.querySelector(pane + ' .lex-pager')
                                    .getBoundingClientRect();
                                const last = rows[rows.length - 1].getBoundingClientRect();
                                return bar.top - last.bottom;
                            }""", pane)
                        assert gap < 6, (pane, gap)
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
    print('DS1 animation panels passed.')


if __name__ == '__main__':
    main()
