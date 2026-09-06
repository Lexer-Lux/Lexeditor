"""Headless editor interactions with synthetic data; no game/ASI testing."""
from pathlib import Path
import argparse
import json
import shutil
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from games.rdr import server
from tools.rdr_test_support import workspace, loot_document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--screenshots', type=Path)
    args = parser.parse_args()
    from playwright.sync_api import sync_playwright
    with tempfile.TemporaryDirectory(prefix='rdr-browser-') as temp, workspace(Path(temp), count=35) as paths:
        service = server.create_server(0)
        thread = threading.Thread(target=service.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as playwright:
                executable = shutil.which('chromium') or shutil.which('chromium-browser')
                browser = playwright.chromium.launch(**({'executable_path': executable} if executable else {}))
                try:
                    page = browser.new_page(viewport={'width': 1600, 'height': 900})
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(f'http://127.0.0.1:{service.server_port}/')
                    page.wait_for_function('typeof state !== "undefined" && !state.booting')
                    assert page.locator('.rdr-record-entry').count(), page.locator('#main').inner_text()
                    for tab in ('items', 'shops', 'missions'):
                        for width, height in ((1600, 900), (1280, 720)):
                            page.set_viewport_size({'width': width, 'height': height})
                            page.evaluate('(tab) => navigate(tab)', tab)
                            page.wait_for_timeout(500)
                            result = page.evaluate('''() => {
                              const list=document.querySelector('.rdr-record-list'),rect=list.getBoundingClientRect();
                              const rows=[...list.querySelectorAll('.rdr-record-entry')];
                              const detail=document.querySelector('.lex-detail'),bounds=detail.getBoundingClientRect();
                              return {rows:rows.length,cut:rows.filter(row=>row.getBoundingClientRect().bottom>rect.bottom+1).length,
                                scroll:list.scrollHeight>list.clientHeight+1,
                                sideBySide:bounds.left>rect.left+rect.width-5,detailWidth:bounds.width,
                                overflow:document.documentElement.scrollWidth>innerWidth};
                            }''')
                            assert result['rows'] and not result['cut'] and not result['scroll'], (tab, result)
                            assert result['sideBySide'] and result['detailWidth'] > 200 and not result['overflow'], (tab, result)
                            print(f'{tab} {width}x{height}: {result}')
                            if args.screenshots:
                                args.screenshots.mkdir(parents=True, exist_ok=True)
                                page.screenshot(path=str(args.screenshots / f'rdr1-{tab}-{width}x{height}.png'))
                    page.evaluate('navigate("items")')
                    page.locator('.item-detail input[type=number]').first.fill('9')
                    page.evaluate('navigate("missions")')
                    page.locator('.mission-detail input[type=number]').first.fill('')
                    requests = []
                    page.on('request', lambda request: requests.append(request.url) if request.method == 'POST' else None)
                    page.evaluate('saveAll()')
                    assert not [url for url in requests if url.endswith('/save')], requests
                    assert page.evaluate('Object.keys(state.itemEdits).length') == 1
                    assert page.get_by_text('Mission 1|cash needs a number', exact=True).count()
                    page.get_by_role('button', name='Confirm and Close').click()
                    page.evaluate('state.itemEdits={};state.missionEdits={};shell.history.clear();navigate("shops")')
                    page.locator('.shop-detail input[type=number]').first.fill('1.1')
                    page.evaluate('saveAll()')
                    assert page.evaluate('dirtyCount()') == 0
                    assert page.locator('.shop-detail input[type=number]').first.input_value() == '1.1'
                    assert server.shops_payload()['rows'][0]['project']
                    page.evaluate('navigate("loot")')
                    page.locator('.loot-table input').first.fill('1.5')
                    assert page.evaluate('state.lootDocument.corpseBonusItem.entries[0].quantity') == 1.5
                    requests.clear()
                    page.evaluate('saveAll()')
                    assert not [url for url in requests if url.endswith('/save')], requests
                    page.get_by_role('button', name='Confirm and Close').click()
                    page.evaluate('switchProjectSource("vanilla")')
                    page.evaluate('switchProjectSource("mine")')
                    assert page.evaluate('state.lootDocument.corpseBonusItem.entries[0].quantity') == 1
                    doc = loot_document()
                    doc.pop('source')
                    paths['LOOT_FILE'].write_text(json.dumps(doc))
                    page.reload()
                    page.wait_for_function('typeof state !== "undefined" && !state.booting')
                    page.evaluate('navigate("loot")')
                    assert page.get_by_text('Not supplied', exact=True).count() == 2
                    paths['LOOT_FILE'].write_text('{broken')
                    page.reload()
                    page.wait_for_function('typeof state !== "undefined" && !state.booting')
                    assert page.locator('.rdr-record-entry').count()
                    page.evaluate('navigate("loot")')
                    assert page.get_by_text('Loot ASI override is unavailable', exact=True).count()
                    page.evaluate('navigate("settings")')
                    assert page.locator('.settings-section').count() == 2
                    page.evaluate('navigate("project")')
                    assert page.get_by_text('Saved files and game delivery', exact=True).count()
                    assert not errors, errors
                    print('RDR browser: split views, preflight, decimal save, loot validation, discard, optional-file recovery passed')
                finally:
                    browser.close()
        finally:
            service.shutdown()
            service.server_close()
            thread.join(timeout=5)


if __name__ == '__main__':
    main()
