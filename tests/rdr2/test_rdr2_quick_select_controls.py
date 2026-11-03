"""The real picker and catalog Save omit automatic order and reload assigned order."""
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from playwright.sync_api import sync_playwright, expect
from plugins.rdr2 import server as s
from test_rdr2_quick_select_batch_validation import quick, fixture
from rdr2_browser_check import document


def test_quick_select_add_saves_automatic_order_through_http(quick):
    _, path = quick
    http = s.create_server(0)
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()
    def request(path, payload=None):
        query = Request(f'http://127.0.0.1:{http.server_port}{path}',
                        data=json.dumps(payload).encode() if payload is not None else None,
                        headers={'Content-Type': 'application/json'})
        try:
            with urlopen(query, timeout=5) as response:
                return {'status': response.status, 'body': json.load(response)}
        except HTTPError as error:
            return {'status': error.code, 'body': json.load(error)}
    try:
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={'width': 1400, 'height': 900})
                page.expose_function('catalogHttp', lambda body: request('/api/catalog/save', body))
                page.expose_function('quickHttp', lambda: request('/api/quick-select'))
                page.route('**/*', lambda route: route.abort())
                page.set_content(document().replace('<head>', '<head><base href="https://lexeditor.test/">', 1))
                page.wait_for_function('!state.booting&&state.catalog?.items?.length')
                page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')")
                page.evaluate('''async()=>{
                  const original=window.fetch;
                  window.fetch=async(url,opts={})=>{
                    const fixture=await original(url,opts);
                    const response=url.startsWith('/api/catalog/save')?await catalogHttp(JSON.parse(opts.body)):
                      url.startsWith('/api/quick-select')?await quickHttp():null;
                    return response?new Response(JSON.stringify(response.body),{status:response.status,headers:{'Content-Type':'application/json'}}):fixture;
                  };
                  window.quickItem={...state.catalog.items[0],key:'FIXTURE'};
                  state.catalog.items=[quickItem];state.quickSelect=await api('/api/quick-select');
                  window.drawQuickFixture=()=>document.querySelector('#main').replaceChildren(
                    LexeditorUI.detailPanel({title:'Fixture',body:[LexeditorUI.detailField({label:'Quick-select slots',control:quickSelectSlotsCell(quickItem)})]}));
                  drawQuickFixture();
                }''')
                page.locator('.quick-select-add').click()
                picker = page.get_by_role('dialog')
                expect(picker).to_be_visible()
                picker.get_by_role('button', name='Slot B', exact=True).click()
                expect(page.get_by_text('order: automatic', exact=True)).to_be_visible()
                assert page.evaluate("state.quickSelectEdits.FIXTURE.slots[1].sortOrder") is None
                page.evaluate('''async()=>{window.__requests=[];await saveCatalog();drawQuickFixture()}''')
                payload = page.evaluate("window.__requests.find(row=>row.path==='/api/catalog/save').body.quickSelect")
                assert payload == [{'item': 'FIXTURE', 'slots': [{'id': 'SLOT_A', 'sortOrder': 10}, {'id': 'SLOT_B'}]}]
                expect(page.get_by_text('order 30', exact=True)).to_be_visible()
                assert page.evaluate('Object.keys(state.quickSelectEdits).length') == 0
                s._files.clear()
                assert s.get_quick_select()['items']['FIXTURE']['slots'] == [
                    {'id': 'SLOT_A', 'sortOrder': 10}, {'id': 'SLOT_B', 'sortOrder': 30}]
                assert s.get_quick_select()['items']['UNTOUCHED']['slots'] == [{'id': 'SLOT_B', 'sortOrder': 20}]
                assert b'<!--preserve-->' in path.read_bytes()
                assert s.load_file(s.QUICK_SELECT_FILE)['root'].find('.//Item[@key="FIXTURE"]/Opaque').get('value') == '17'
                page.evaluate("state.ds='vanilla';drawQuickFixture()")
                expect(page.locator('.quick-select-add')).to_have_count(0)
                for select in page.locator('#main select').all():
                    expect(select).to_be_disabled()
            finally:
                browser.close()
    finally:
        http.shutdown()
        http.server_close()
        worker.join()
