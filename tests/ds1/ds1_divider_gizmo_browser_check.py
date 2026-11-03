"""Divider gizmos meet the cursor where it hovers, not at the middle.

Hovering the list/detail divider at several heights puts the visible
Barrels/Columns gizmo under the cursor (clamped to the strip) at full
opacity, on a plain and on a multi-barrel master alike. The gizmo's
barrel +/- buttons click through a full roundtrip, dismiss on mouse-away
after a click, and parking the mouse on the detail header's preview
thumbnail never summons the gizmo: it only appears over the divider strip
itself.
"""
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests' / 'ds1'))
from ds1_fixture import make_archive  # noqa: E402
from plugins.ds1.formats import ItemDocument  # noqa: E402
from plugins.ds1.store import RELATIVE, MARKER  # noqa: E402
from plugins.ds1.plugin import DS1Session  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


def check(page, rows):
    box = page.locator(
        '.lex-panel-layout-divider:has(> .lex-barrel-control)').first.bounding_box()
    cx = box['x'] + box['width'] / 2
    for frac in (0.1, 0.3, 0.5, 0.7, 0.9):
        want = box['y'] + box['height'] * frac
        page.mouse.move(cx, want)
        time.sleep(0.35)
        info = page.evaluate('''(want) => {
            const vis = [...document.querySelectorAll(
                '.lex-panel-layout-divider > .lex-barrel-control')].filter(
                g => g.getBoundingClientRect().width > 0);
            if (!vis.length) return null;
            const rect = vis[0].getBoundingClientRect();
            return {opacity: getComputedStyle(vis[0]).opacity,
                    cy: rect.y + rect.height / 2, want};
        }''', arg=want)
        assert info is not None, f'gizmo visible at {rows} rows, y={want:.0f}'
        assert info['opacity'] == '1', f'gizmo opaque at y={want:.0f}'
        assert abs(info['cy'] - info['want']) <= 2, (
            f"gizmo at {info['cy']:.0f}, cursor at {info['want']:.0f}")


def click_roundtrip(page):
    strip = page.locator(
        '.lex-panel-layout-divider:has(> .lex-barrel-control)').first
    box = strip.bounding_box()
    page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
    time.sleep(0.35)
    control = page.locator(
        '.lex-panel-layout-divider > .lex-barrel-control').first
    value = control.locator('.lex-barrel-count').first
    assert value.text_content().strip() == '1', 'barrels start at 1'
    control.locator('.lex-barrel-increase').first.click()
    page.wait_for_function(
        """() => [...document.querySelectorAll(
        '.lex-panel-layout-divider > .lex-barrel-control .lex-barrel-count'
        )].some(el => el.textContent.trim() === '2')""")
    assert value.text_content().strip() == '2', 'barrel + reaches 2'
    box = strip.bounding_box()
    page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
    time.sleep(0.35)
    control.locator('.lex-barrel-decrease').first.click()
    page.wait_for_function(
        """() => [...document.querySelectorAll(
        '.lex-panel-layout-divider > .lex-barrel-control .lex-barrel-count'
        )].some(el => el.textContent.trim() === '1')""")
    assert value.text_content().strip() == '1', 'barrel - returns to 1'
    page.mouse.move(box['x'] + 400, box['y'] + box['height'] / 2)
    time.sleep(0.35)
    shown = page.evaluate("""() => [...document.querySelectorAll(
        '.lex-panel-layout-divider > .lex-barrel-control')].filter(
        g => parseFloat(getComputedStyle(g).opacity) > 0).length""")
    assert shown == 0, 'gizmo dismisses after +/- click and mouse-away'


def phantom_probe(page):
    strip = page.locator(
        '.lex-panel-layout-divider:has(> .lex-barrel-control)').first
    box = strip.bounding_box()
    thumb = page.locator('.lex-detail-header .lex-detail-panel-icon, '
                         '.lex-detail-panel-icon').first.bounding_box()
    assert thumb is not None, 'header thumbnail present'
    cy = min(max(thumb['y'] + thumb['height'] / 2, box['y'] + 8),
             box['y'] + box['height'] - 8)
    page.mouse.move(box['x'] + box['width'] / 2, cy)
    time.sleep(0.35)
    shown = page.evaluate("""() => [...document.querySelectorAll(
        '.lex-panel-layout-divider > .lex-barrel-control')].filter(
        g => parseFloat(getComputedStyle(g).opacity) > 0).length""")
    assert shown > 0, 'gizmo summons over the divider strip'
    page.mouse.move(thumb['x'] + thumb['width'] / 2,
                    thumb['y'] + thumb['height'] / 2)
    time.sleep(0.35)
    shown = page.evaluate("""() => [...document.querySelectorAll(
        '.lex-panel-layout-divider > .lex-barrel-control')].filter(
        g => parseFloat(getComputedStyle(g).opacity) > 0).length""")
    assert shown == 0, 'header thumbnail hover summons no gizmo'


def main():
    errors = []
    for count in (4, 60):
        document = ItemDocument(make_archive(
            {'EquipParamGoods': list(range(100, 100 + count))}))
        raw = document.export()
        with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-gizmo-') as temp:
            temp = Path(temp)
            game, mod = temp / 'game', temp / 'mod'
            (game / RELATIVE).parent.mkdir(parents=True)
            (game / RELATIVE).write_bytes(raw)
            mod.mkdir()
            (mod / MARKER).touch()
            session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game),
                                  'LEXEDITOR_DS1_PROJECT': str(mod),
                                  'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0'})
            try:
                session.start()
                with sync_playwright() as play:
                    browser = play.chromium.launch(headless=True)
                    try:
                        page = browser.new_page(viewport={'width': 1280, 'height': 900})
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        page.goto(session.url)
                        page.wait_for_selector('body[data-ds1-ready="true"]')
                        page.wait_for_function(
                            'document.querySelector(".lex-plugin-loading-screen") === null',
                            timeout=30000)
                        page.wait_for_function('state.pending === 0', timeout=30000)
                        page.locator(
                            '.lex-list-row[data-key="EquipParamGoods:100"]').click()
                        page.wait_for_function(
                            '`${state.row.table}:${state.row.id}` === "EquipParamGoods:100"')
                        check(page, count)
                        if count == 60:
                            click_roundtrip(page)
                            phantom_probe(page)
                    finally:
                        browser.close()
            finally:
                session.stop()
    assert not errors, errors
    print('DS1 divider gizmo browser check passed')


if __name__ == '__main__':
    main()
