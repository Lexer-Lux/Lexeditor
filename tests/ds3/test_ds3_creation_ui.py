"""Each supported PARAM family can be copied, exported and reopened in the UI."""
from pathlib import Path

from playwright.sync_api import sync_playwright

from core.service_session import LocalPluginSession
from plugins.ds3.formats import RegulationDocument, TARGET_TABLES, encrypt_regulation
from test_ds3_plugin import _bnd4, METADATA


def test_shared_add_saves_and_reopens_every_supported_table(tmp_path):
    root = Path(__file__).resolve().parents[2]
    source = tmp_path / 'installed-Data0.bdt'
    source.write_bytes(encrypt_regulation(_bnd4(), iv=b'\x51' * 16))
    original = source.read_bytes()
    baseline = RegulationDocument(original, METADATA)
    project = tmp_path / 'project'
    project.mkdir()
    (project / '.lexeditor-ds3-project').write_text('{"schema":1,"game":"Dark Souls III"}\n')
    session = LocalPluginSession(module='plugins.ds3.server', plugin_id='ds3', app_root=root,
        check=lambda: [], extra_env={'LEXEDITOR_DS3_SOURCE': str(source),
            'LEXEDITOR_DS3_PROJECT': str(project), 'LEXEDITOR_DS3_ROOT': str(tmp_path / 'game'),
            'LEXEDITOR_MOD_READ_ONLY': '0', 'LEXEDITOR_NO_MOD': '0'})
    session.start()
    try:
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={'width': 1440, 'height': 900})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(session.url)
                page.wait_for_function('!state.booting')
                page.locator('.lex-plugin-loading-screen').wait_for(state='detached')
                for table in TARGET_TABLES:
                    page.evaluate('table=>navigate(table)', table)
                    new_id = max(row.row_id for row in baseline.params[table].rows) + 1
                    name = 'Created ' + table
                    page.locator('.lex-table-add').click()
                    page.get_by_label('New record ID', exact=True).fill(str(new_id))
                    page.get_by_label('New record name', exact=True).fill(name)
                    page.get_by_role('button', name='Create record', exact=True).click()
                    page.wait_for_function('state.dirty===1')
                    page.locator('#global-save').click()
                    page.wait_for_function('state.dirty===0')
                    reopened = RegulationDocument((project / 'Data0.bdt').read_bytes(), METADATA)
                    assert reopened.read_row(table, new_id)['name'] == name
                    assert len(reopened.params[table].rows) == len(baseline.params[table].rows) + 1
                    for row in baseline.params[table].rows:
                        assert reopened.read_row(table, row.row_id) == baseline.read_row(table, row.row_id)
                    assert source.read_bytes() == original
                    page.reload()
                    page.wait_for_function('!state.booting')
                    page.locator('.lex-plugin-loading-screen').wait_for(state='detached')
                    page.evaluate('table=>navigate(table)', table)
                    page.wait_for_function('({table,id})=>state.tables[table].rows.some(row=>row.id===id&&row.created)',
                        arg={'table': table, 'id': new_id})
                    cell = page.locator('.ds3-layout .lex-column-list-cell[data-column-key="name"]').filter(has_text=name)
                    cell.wait_for(state='visible')
                    assert cell.count() == 1
                    assert not errors, errors
            finally:
                browser.close()
    finally:
        session.stop()
