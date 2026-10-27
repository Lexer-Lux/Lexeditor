"""Maps side panels page what fits, with the pager inside the panel.

Every list in the app sizes its page to the visible area so a paged list
never scrolls, and each list's pagination bar lives in that list's own
panel. The Maps tab broke both rules: the left Directory list showed a
pager AND a scrollbar, the right Placements list scrolled while its
pager sat fixed across the whole window bottom, and the Maps list had
no pager at all. All three now use the shared fitted paged pane (the
same one the Animations side panels use).
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests' / 'ds1'))
from ds1_fixture import make_archive  # noqa: E402
from msb_fixture import build_msb  # noqa: E402
from plugins.ds1.msb import MAP_DIR  # noqa: E402
from plugins.ds1.store import RELATIVE  # noqa: E402
from plugins.ds1.plugin import DS1Session  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

MAPS = [f"m10_{area:02d}_00_00.msb" for area in range(45)]
BIG_MAP = MAPS[0]

PANEL_STATE = """(pair) => {
    const root = document.querySelector(pair[0]);
    const node = root ? root.querySelector(pair[1]) : null;
    const bar = root ? root.querySelector('.lex-pager') : null;
    if (!root || !node || !bar) return null;
    const box = root.getBoundingClientRect();
    const pager = bar.getBoundingClientRect();
    return {
        scrollable: node.scrollHeight > node.clientHeight + 1,
        rows: node.querySelectorAll('.lex-list-row:not(.lex-filler-row)').length,
        pagerInside: pager.top >= box.top - 1 && pager.bottom <= box.bottom + 1
            && pager.left >= box.left - 1 && pager.right <= box.right + 1,
        pagerInline: bar.classList.contains('lex-pager-inline'),
    };
}"""


def panel_settled(page, panel, list_selector):
    page.wait_for_function(
        '(pair) => { const state = (' + PANEL_STATE + ')(pair);'
        ' return state !== null && state.scrollable === false; }',
        arg=[panel, list_selector], timeout=15000)
    # The fitted page size converges a beat after the rows render: a tab
    # rebuilt with the previous height's size looks settled until the
    # refit lands, so wait for the count to stop changing.
    page.wait_for_function(
        '(pair) => {'
        ' const root = document.querySelector(pair[0]);'
        ' const node = root ? root.querySelector(pair[1]) : null;'
        ' if (!node) return false;'
        ' const rows = node.querySelectorAll(".lex-list-row:not(.lex-filler-row)").length;'
        ' const key = pair[0] + "|" + pair[1];'
        ' const last = (window.__lex_paging_last_count || {})[key];'
        ' (window.__lex_paging_last_count = window.__lex_paging_last_count || {})[key] = rows;'
        ' return last === rows; }',
        arg=[panel, list_selector], timeout=15000)


def check_panel(page, panel, list_selector, label):
    state = page.evaluate(PANEL_STATE, [panel, list_selector])
    assert state is not None, f"{label}: panel, list or pager missing"
    assert not state['scrollable'], f"{label}: paged list scrolls"
    assert state['pagerInline'], f"{label}: pager is not the inline variant"
    assert state['pagerInside'], f"{label}: pager escapes its panel"
    return state


def test_maps_side_panels_fit_and_page_inside():
    shots = Path(tempfile.gettempdir()) / 'lexeditor-dev'
    shots.mkdir(parents=True, exist_ok=True)
    parts = tuple(('enemy', 2, index, 0, 120000) for index in range(60))
    raw = make_archive()
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-maps-paging-') as folder:
        temp = Path(folder)
        game = temp / 'game'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(raw)
        (game / MAP_DIR).mkdir(parents=True)
        for name in MAPS:
            body = build_msb(parts=parts) if name == BIG_MAP else build_msb()
            (game / MAP_DIR / name).write_bytes(body)
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_NO_MOD': '1',
                              'LEXEDITOR_MOD_READ_ONLY': '1'})
        errors = []
        session.start()
        try:
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=60000)
                    page.locator('button[data-tab="maps"]').click()
                    page.wait_for_function(
                        'state.tab==="maps" && state.mapView && state.rows.length>0'
                        ' && !state.error', timeout=60000)
                    sizes = {}
                    side_tall = None
                    for height in (900, 600):
                        if height != 900:
                            page.set_viewport_size({'width': 1440, 'height': height})
                            # The fitted page derives from the panel height,
                            # which follows the viewport asynchronously:
                            # measure only after the panel actually shrinks,
                            # or the tall fit reads back stale.
                            page.wait_for_function(
                                'tall => document.querySelector("[data-maps-side]")'
                                '.getBoundingClientRect().height < tall',
                                arg=side_tall, timeout=15000)
                        page.locator('[data-tabstrip-id="placements"]').click()
                        page.wait_for_function('state.mapTab==="placements"',
                                               timeout=30000)
                        subtabs = (('drops', 'Drops'), ('treasure', 'Treasure'),
                                   ('npcs', 'NPCs'), ('enemies', 'Enemies'))
                        for subtab, label in subtabs:
                            page.locator('[data-maps-dir] .lex-subtab-button',
                                         has_text=label).click()
                            page.wait_for_function(f'state.dirTab==="{subtab}"',
                                                   timeout=30000)
                            panel_settled(page, '[data-maps-dir]', '.lex-column-list')
                            check_panel(page, '[data-maps-dir]', '.lex-column-list',
                                        f'directory/{subtab} at height {height}')
                        assert page.locator(
                            '#main .lex-pager:not(.lex-pager-inline)').count() == 0
                        for tab in ('maps', 'placements'):
                            page.locator(f'[data-tabstrip-id="{tab}"]').click()
                            page.wait_for_function(f'state.mapTab==="{tab}"',
                                                   timeout=30000)
                            panel_settled(page, '[data-maps-side]', '.lex-column-list')
                            state = check_panel(page, '[data-maps-side]',
                                                '.lex-column-list',
                                                f'side/{tab} at height {height}')
                            sizes[(tab, height)] = state['rows']
                        assert page.locator(
                            '#main .lex-pager:not(.lex-pager-inline)').count() == 0
                        page.wait_for_timeout(300)
                        page.screenshot(path=str(shots / f'maps-panel-paging-{height}.png'))
                        if height == 900:
                            side_tall = page.evaluate(
                                'document.querySelector("[data-maps-side]")'
                                '.getBoundingClientRect().height')
                    # Taller window, more rows per page: the page size is
                    # derived from the panel height, not fixed.
                    assert sizes[('placements', 900)] > sizes[('placements', 600)], sizes
                    assert sizes[('maps', 900)] > sizes[('maps', 600)], sizes
                    # Paging still works through the in-panel bar.
                    page.set_viewport_size({'width': 1440, 'height': 900})
                    page.wait_for_function(
                        'tall => document.querySelector("[data-maps-side]")'
                        '.getBoundingClientRect().height >= tall - 1',
                        arg=side_tall, timeout=15000)
                    page.locator('[data-tabstrip-id="placements"]').click()
                    page.wait_for_function('state.mapTab==="placements"', timeout=30000)
                    page.locator('[data-maps-dir] .lex-subtab-button', has_text='All').click()
                    page.wait_for_function('state.dirTab==="all"', timeout=30000)
                    panel_settled(page, '[data-maps-side]', '.lex-column-list')
                    keys = ("[data-maps-side] .lex-list-row:not(.lex-filler-row)",)
                    first = page.locator(keys[0]).evaluate_all(
                        'nodes => nodes.map(node => node.dataset.key)')
                    assert len(first) > 1, first
                    page.locator('[data-maps-side]').get_by_role(
                        'button', name='Next page').click()
                    page.wait_for_function('state.page===1', timeout=30000)
                    panel_settled(page, '[data-maps-side]', '.lex-column-list')
                    second = page.locator(keys[0]).evaluate_all(
                        'nodes => nodes.map(node => node.dataset.key)')
                    assert first != second, (first, second)
                    assert not set(first) & set(second), (first, second)
                    check_panel(page, '[data-maps-side]', '.lex-column-list',
                                'side/placements page two')
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
