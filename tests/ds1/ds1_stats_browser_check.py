"""Render the Stats tab's three lists and edit/save/reload, never game files."""
import hashlib
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests' / 'shared'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paged_detail import reveal
from ds1_fixture import make_archive, make_text_archive
from ds1_stats_fixture import make_stats_archive
from plugins.ds1 import texts
from plugins.ds1.formats import ItemDocument, STATS_FIELDS, STATS_SUBTABS
from plugins.ds1.store import RELATIVE, MARKER
from plugins.ds1.plugin import DS1Session
from core.service_session import request_json
from playwright.sync_api import sync_playwright


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
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_DS1_PROJECT': str(mod),
                              'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0'})
        errors, changes = [], []
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
                        else:
                            assert set(keys) == set(STATS_FIELDS[table]), keys
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
                        changes.append((identity['table'], identity['id'], field, value))
                        if output:
                            page.screenshot(path=str(output / f'stats-{tab}.png'))
                    page.locator('#global-save').click()
                    page.wait_for_function('state.dirty===0 && state.pending===0')
                    page.reload()
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    reopened = ItemDocument((mod / RELATIVE).read_bytes())
                    for table, row_id, field, value in changes:
                        assert reopened.value(table, row_id, field) == value
                    assert not errors, errors
                finally:
                    browser.close()
            assert (game / RELATIVE).read_bytes() == raw
            assert hashlib.sha256(raw).hexdigest() == source_hash
        finally:
            session.stop()
            assert session.wait_closed()
        # Without the curve table, Stats opens on weapon scaling, not an error.
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
                    page.wait_for_function('state.tab==="stats" && state.sub==="scaling" && state.rows.length>0 && state.rows[0].table==="EquipParamWeapon" && !state.error')
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
    print('DS1 Stats lists, filtered details, curve groups, save/reload and missing-curve fallback passed.')


if __name__ == '__main__':
    main()
