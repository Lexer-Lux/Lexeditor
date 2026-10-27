"""Render the Stats tab's lists and edit/save/reload, never game files."""
import hashlib
import os
import shutil
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests' / 'shared'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paged_detail import reveal
from ds1_fixture import make_archive, make_menu_archive, make_text_archive
from ds1_stats_fixture import make_stats_archive
from plugins.ds1 import levelup_gains, texts
from plugins.ds1.charainit import GIFT_FIELDS
from plugins.ds1.formats import ItemDocument, STATS_FIELDS, STATS_SUBTABS
from plugins.ds1.store import RELATIVE, MARKER
from plugins.ds1.plugin import DS1Session
from core.service_session import request_json
from playwright.sync_api import sync_playwright


def select_filled_slot(page, session, tab, table, key):
    """Open the first listed row whose `key` slot holds an item.

    Both -1 and 0 read as None for starting kits and materials, so
    anything else is a filled slot, in fixtures and the shipped game alike.
    The master list pages client-side while state.rows holds every row, so
    only visible rows are candidates, page by page from the first.
    """
    first = page.get_by_role('button', name='First page', exact=True)
    if first.count():
        first.first.click()
        page.wait_for_timeout(600)
    for _ in range(100):
        for data_key in page.locator('.lex-list-row[data-key]').evaluate_all(
                'nodes=>nodes.map(n=>n.dataset.key)'):
            head, _, tail = data_key.partition(':')
            if head != table or not tail.lstrip('-').isdigit():
                continue
            row_id = int(tail)
            candidate = request_json(session.url + f"api/row?table={table}&id={row_id}&sub={tab}")['row']
            if next(f['value'] for f in candidate['fields'] if f['key'] == key) not in (-1, 0, None):
                if page.evaluate('state.row && state.row.id') != row_id:
                    page.locator(f'.lex-list-row[data-key="{data_key}"]').click()
                    page.wait_for_function(f'state.row && state.row.id==={row_id} && !state.error')
                return
        following = page.get_by_role('button', name='Next page', exact=True)
        if not following.count() or not following.first.is_enabled():
            break
        following.first.click()
        page.wait_for_timeout(600)
    raise AssertionError(f'no {table} row fills {key}')


def pair_widths(page, prop):
    """Item-half, count-half and em widths of one item/count pair row."""
    return page.evaluate("""(prop) => {
        const group = document.querySelector(`[data-lex-property="${prop}"] .lex-detail-parts`);
        const parts = [...group.children];
        return {item: parts[0].getBoundingClientRect().width,
                count: parts[1].getBoundingClientRect().width,
                em: parseFloat(getComputedStyle(group).fontSize)};
    }""", prop)


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    real_root = os.environ.get('LEXEDITOR_DS1_ACCEPTANCE_ROOT')
    original_path = Path(real_root) / RELATIVE if real_root else None
    raw = original_path.read_bytes() if original_path else make_stats_archive()
    source_hash = hashlib.sha256(raw).hexdigest()
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-stats-') as folder:
        temp = Path(folder)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(raw)
        (game / texts.RELATIVE).parent.mkdir(parents=True)
        (game / texts.RELATIVE).write_bytes((Path(real_root) / texts.RELATIVE).read_bytes() if real_root else make_text_archive())
        (game / texts.MENU_RELATIVE).parent.mkdir(parents=True, exist_ok=True)
        (game / texts.MENU_RELATIVE).write_bytes(
            (Path(real_root) / texts.MENU_RELATIVE).read_bytes() if real_root else make_menu_archive(
                extra={texts.CLASS_DESCRIPTION_FILE: {
                    132320: 'Warrior test.', 132355: 'Gift test.', 132357: 'Gift test.'}}))
        if real_root:
            # Label art reads the installed menu archives, so the
            # acceptance run carries them (~32MB); fixtures have none.
            (game / 'menu').mkdir(parents=True)
            for name in ('menu.drb', 'menu_0.tpf.dcx', 'menu_1.tpf.dcx',
                         'menu_2.tpf.dcx', 'menu_3.tpf.dcx',
                         'menu_4.tpf.dcx', 'menu_5.tpf.dcx'):
                shutil.copy(Path(real_root) / 'menu' / name, game / 'menu' / name)
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_DS1_PROJECT': str(mod),
                              'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0'})
        errors, changes = [], []
        gains_change = None
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    page.locator('button[data-tab="stats"]').click()
                    # The tab and subtab flip before the new rows arrive, so the
                    # wait names the new rows' table; stale rows would pass it.
                    page.wait_for_function('state.tab==="stats" && state.sub==="curves" && state.rows.length>0 && state.rows[0].table==="CalcCorrectGraph" && state.row && state.row.table==="CalcCorrectGraph" && !state.error')
                    # Subtabs read alphabetically, as on every page (the shared bar's rule).
                    assert page.locator('[data-subtab]').evaluate_all('nodes=>nodes.map(n=>n.dataset.subtab)') == \
                        [t[0] for t in sorted(STATS_SUBTABS, key=lambda t: t[1].casefold())]
                    for tab, _, table in STATS_SUBTABS:
                        page.locator(f'[data-subtab="{tab}"]').click()
                        page.wait_for_function('(want)=>state.sub===want.tab && state.rows.length>0 && state.rows[0].table===want.table && state.row && state.row.table===want.table && !state.error', arg={'tab': tab, 'table': table})
                        page.wait_for_timeout(200)
                        assert page.evaluate('state.rows.length') > 0
                        assert page.locator('.lex-column-list .lex-list-row').count() > 0
                        keys = page.evaluate('state.row.fields.map(f=>f.key)')
                        if table == 'CalcCorrectGraph':
                            assert set(keys) == set(STATS_FIELDS[table]), keys
                            groups = page.evaluate('[...new Set(state.row.fields.map(f=>f.group))]')
                            assert groups == ['Thresholds', 'Growth', 'Curve shape', 'Level-up cost'], groups
                            assert page.locator('.lex-curve-editor[data-curve-row]').count() == 1
                            curve = page.evaluate("""() => {
                                const card = document.querySelector('.lex-curve-editor[data-curve-row]');
                                const read = key => Number(document.querySelector(`input[data-field-key="${key}"]`).value);
                                const stages = [0, 1, 2, 3, 4].map(i => read(`stageMaxVal${i}`));
                                const growth = [0, 1, 2, 3, 4].map(i => read(`stageMaxGrowVal${i}`));
                                return {at: stages.map(s => card.curveEvaluate(s)), growth,
                                        mid: card.curveEvaluate((stages[0] + stages[1]) / 2)};
                            }""")
                            for value, expected in zip(curve['at'], curve['growth']):
                                assert abs(value - expected) < 1e-6, (value, expected)
                            low, high = sorted((curve['growth'][0], curve['growth'][1]))
                            assert low <= curve['mid'] <= high, curve
                            page.locator('.lex-list-row[data-key="CalcCorrectGraph:0"]').click()
                            page.wait_for_function('state.row && state.row.id===0 && !state.error')
                            # Each span draws its own equation, titled after
                            # the Y axis, as on FF8's curves.
                            card = page.locator('.lex-curve-editor[data-curve-row]')
                            follows = card.locator('.lex-curve-math-follow')
                            assert follows.count() == 4
                            assert follows.evaluate_all(
                                'nodes=>nodes.map(n=>n.getAttribute("aria-label"))') == [
                                f'Scaling(x) = V{i + 1} + (V{i + 2} - V{i + 1})'
                                f' * ((x - T{i + 1})/(T{i + 2} - T{i + 1}))^S{i + 1}'
                                for i in range(4)]
                            assert card.locator('.lex-curve-math-atom').count() > 0
                            # Axes in player terms, with the shared unit.
                            assert card.locator(
                                '.lex-curve-axis-name-x').inner_text() == 'Stat'
                            y_axis = card.locator('.lex-curve-axis-name-y')
                            assert 'Scaling' in y_axis.inner_text()
                            assert y_axis.locator('.lex-unit').inner_text() == '%'
                            # Every drawer variable carries its own help.
                            assert card.locator(
                                '.lex-curve-variable .lex-info-help').count() == 19
                        elif tab == 'starting-gifts':
                            assert set(keys) == set(GIFT_FIELDS), keys
                        elif tab == 'levelup':
                            assert set(keys) == {name for name, _, _ in levelup_gains.INPUTS}, keys
                            # Nine stat icons on the weights, four defense
                            # icons on the rows, through the shared label art.
                            assert page.locator('.lex-detail-panel [data-lex-icon]').count() == 9
                            assert page.evaluate('state.rows.map(r=>r.labelKind)') == [
                                levelup_gains.ROW_ICONS[key] for key, _ in levelup_gains.OUTPUTS]
                            # The weights are gains, not the stats: each
                            # reads '{stat} gain' with a /level unit.
                            for name, stat, _ in levelup_gains.INPUTS:
                                cell = page.locator(
                                    f'[data-lex-layout-field="{name}"]')
                                assert cell.locator(
                                    '.lex-detail-field-label-text').inner_text() == f'{stat} gain'
                                assert cell.locator('.lex-unit').inner_text() == '/level'
                            if real_root:
                                page.wait_for_function(
                                    "() => [...document.querySelectorAll("
                                    "'.lex-detail-panel [data-lex-icon] img.lex-ds1-label-art')]"
                                    ".filter(img => img.naturalWidth > 0).length === 9")
                                page.evaluate('state.pagedView.pinOwner.toggle("icon","Icon")')
                                page.wait_for_function(
                                    "() => document.querySelectorAll("
                                    "'.lex-list-row img[src*=\"/api/label\"]').length === 4")
                        else:
                            assert set(keys) == set(STATS_FIELDS[table]), keys
                        if tab == 'starting-classes':
                            # Each starting item shares its row with its
                            # count; no count stands alone anymore.
                            for item, num in (('item_09', 'itemNum_09'), ('item_10', 'itemNum_10')):
                                pair = page.locator(f'[data-lex-property="{item}"]')
                                assert pair.count() == 1
                                assert pair.locator(f'[data-field-key="{item}"]').count() == 1
                                assert pair.locator(f'input[data-field-key="{num}"]').count() == 1
                            assert page.locator('[data-lex-property="itemNum_09"]').count() == 0
                            # The pair's room goes to the item: on a row with a
                            # filled slot the item half is wider than the count
                            # half and reads at least 8em, and an empty slot's
                            # select shows None as wide as a Ring select.
                            select_filled_slot(page, session, tab, table, 'item_09')
                            reveal(page, page.locator('[data-lex-property="item_09"]'))
                            sizes = pair_widths(page, 'item_09')
                            assert sizes['item'] > sizes['count'], sizes
                            assert sizes['item'] >= 8 * sizes['em'], sizes
                            # A changed count shares its box with the vanilla
                            # reference and the stepper; three digits still show.
                            count = page.locator('input[data-field-key="itemNum_09"]')
                            before = count.input_value()
                            count.fill('300')
                            count.press('Tab')
                            page.wait_for_function('state.pending===0')
                            page.wait_for_timeout(200)
                            reveal(page, page.locator('[data-lex-property="item_09"]'))
                            assert page.locator('[data-lex-property="item_09"] .lex-reference-values').count() == 1
                            fit = page.evaluate("""() => {
                                const box = document.querySelector('input[data-field-key="itemNum_09"]');
                                const style = getComputedStyle(box);
                                const pen = document.createElement('canvas').getContext('2d');
                                pen.font = style.font;
                                return {text: pen.measureText(box.value).width,
                                        room: box.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight)};
                            }""")
                            assert fit['text'] <= fit['room'], fit
                            if output:
                                page.screenshot(path=str(output / 'stats-starting-classes-count.png'))
                            count.fill(before)
                            count.press('Tab')
                            page.wait_for_function('state.pending===0')
                            sizes = pair_widths(page, 'item_09')
                            assert sizes['item'] >= 8 * sizes['em'], sizes
                            # Reference slots keep a face and a finder, never a
                            # full-table select, empty ones included: the face
                            # names the pick (None here) and the finder changes it.
                            for prop in ("item_01", "equip_Accessory02"):
                                assert page.locator(f'[data-lex-property="{prop}"] select').count() == 0
                                assert page.locator(f'[data-lex-property="{prop}"] .ds1-reference-face').count() == 1
                                assert page.locator(f'[data-lex-property="{prop}"] .ds1-find-reference').count() == 1
                            assert "None" in page.locator('[data-lex-property="item_01"] .ds1-reference-face').inner_text()
                        elif tab == 'starting-gifts':
                            pair = page.locator('[data-lex-property="item_01"]')
                            assert pair.count() == 1
                            assert pair.locator('input[data-field-key="itemNum_01"]').count() == 1
                        elif tab == 'upgrade-materials':
                            pair = page.locator('[data-lex-property="materialId01"]')
                            assert pair.count() == 1
                            assert pair.locator('input[data-field-key="itemNum01"]').count() == 1
                            # The same shared pair: the filled material's name
                            # gets the room, the count keeps its narrow box.
                            select_filled_slot(page, session, tab, table, 'materialId01')
                            reveal(page, page.locator('[data-lex-property="materialId01"]'))
                            sizes = pair_widths(page, 'materialId01')
                            assert sizes['item'] > sizes['count'], sizes
                            assert sizes['item'] >= 8 * sizes['em'], sizes
                        control = reveal(page, page.locator('input[data-field-key][type="number"]').first)
                        field = control.get_attribute('data-field-key')
                        old = float(control.input_value().replace(',', ''))
                        low, high = float(control.get_attribute('min')), float(control.get_attribute('max'))
                        value = min(max(old + 1, low), high)
                        if value == old:
                            value = max(low, old - 1)
                        assert value != old
                        identity = page.evaluate('({table:state.row.table,id:state.row.id})')
                        control.fill(str(int(value)) if value.is_integer() else str(value))
                        control.press('Tab')
                        page.wait_for_function('state.pending===0 && state.dirty>0')
                        row = request_json(session.url + f"api/row?table={identity['table']}&id={identity['id']}&sub={tab}")['row']
                        assert next(f['value'] for f in row['fields'] if f['key'] == field) == value
                        # The detail stays filtered after the edit round-trip.
                        assert {f['key'] for f in page.evaluate('state.row.fields')} == set(keys)
                        if tab == 'levelup':
                            gains_change = (identity['id'], field, value)
                        else:
                            changes.append((identity['table'], identity['id'], field, value))
                        if output:
                            page.screenshot(path=str(output / f'stats-{tab}.png'))
                    # The level-up cost row plots its graph like every other curve;
                    # its values stay editable in the variables drawer.
                    page.locator('[data-subtab="curves"]').click()
                    page.wait_for_function('state.sub==="curves" && state.rows.length>0 && !state.error')
                    page.locator('.lex-list-row[data-key="CalcCorrectGraph:200"]').click()
                    page.wait_for_function('state.row && state.row.id===200 && !state.error')
                    assert page.locator('.lex-curve-editor[data-curve-row]').count() == 1
                    assert {field.get_attribute('data-field-key') for field in
                            page.locator('input[data-field-key]').all()} == {
                        'init_inclination_soul', 'adjustment_value',
                        'boundry_inclination_soul', 'boundry_value'}
                    cost = page.locator('.lex-curve-editor[data-curve-row]')
                    assert cost.locator(
                        '.lex-curve-axis-name-x').inner_text() == 'Level'
                    assert 'Souls' in cost.locator(
                        '.lex-curve-axis-name-y').inner_text()
                    assert cost.locator('.lex-curve-math-follow').count() == 1
                    assert cost.locator('.lex-curve-math-follow').get_attribute(
                        'aria-label').startswith('Souls(L) =')
                    assert cost.locator(
                        '.lex-curve-variable .lex-info-help').count() == 4
                    page.locator('#global-save').click()
                    page.wait_for_function('state.dirty===0 && state.pending===0')
                    page.reload()
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    reopened = ItemDocument((mod / RELATIVE).read_bytes())
                    for table, row_id, field, value in changes:
                        assert reopened.value(table, row_id, field) == value
                    assert gains_change is not None
                    row_id, field, value = gains_change
                    again = request_json(session.url + f"api/row?table=NativeRules&id={row_id}&sub=levelup")['row']
                    assert next(f['value'] for f in again['fields'] if f['key'] == field) == value
                    assert not errors, errors
                finally:
                    browser.close()
            assert (game / RELATIVE).read_bytes() == raw
            assert hashlib.sha256(raw).hexdigest() == source_hash
        finally:
            session.stop()
            assert session.wait_closed()
        # Without the curve table, Stats opens on the first list with rows, not an error.
        plain_game, plain_mod = temp / 'plain-game', temp / 'plain-mod'
        (plain_game / RELATIVE).parent.mkdir(parents=True)
        (plain_game / RELATIVE).write_bytes(make_archive())
        plain_mod.mkdir()
        (plain_mod / MARKER).touch()
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(plain_game), 'LEXEDITOR_DS1_PROJECT': str(plain_mod),
                              'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0'})
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    page.locator('button[data-tab="stats"]').click()
                    page.wait_for_function('state.tab==="stats" && state.sub==="weapon-upgrades" && state.rows.length>0 && state.rows[0].table==="ReinforceParamWeapon" && !state.error')
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
    print('DS1 Stats lists, details, curve groups, save/reload and missing-curve fallback passed.')


if __name__ == '__main__':
    main()
