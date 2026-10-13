"""Crime detail drafts retain exact values and reject before any writer runs."""
import sys
import json
import threading
from urllib.request import Request, urlopen
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

sys.path.insert(0,str(Path(__file__).resolve().parent))
from rdr2_browser_check import document
from rdr2_tables_browser_check import CRIME_FIELDS
from plugins.rdr2 import server as s


def test_crime_shared_name_edits_persist_without_renaming_ids(tmp_path, monkeypatch):
    labels = tmp_path / 'labels.json'
    labels.write_text(json.dumps({'crimes': {'CRIME_OTHER': 'Other label'}}))
    monkeypatch.setattr(s, 'LABELS_FILE', labels)
    http = s.create_server(0)
    worker = threading.Thread(target=http.serve_forever, daemon=True);worker.start()
    def label_api(_source, path, body=None):
        assert path in {'/api/labels', '/api/labels/save'}
        request = Request(f'http://127.0.0.1:{http.server_port}{path}',
            data=None if body is None else json.dumps(body).encode(),
            headers={'Content-Type': 'application/json'})
        with urlopen(request, timeout=5) as response:
            return json.load(response)
    try:
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={'width': 1400, 'height': 1100})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.route('**/*', lambda route: route.abort())
                page.set_content(document().replace('<head>', '<head><base href="https://lexeditor.test/">', 1))
                page.wait_for_function('!state.booting&&state.catalog?.items?.length')
                page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')")
                page.expose_binding('crimeLabelApi', label_api)
                page.evaluate('''async fields=>{
                  const original=window.fetch;
                  window.fetch=async(url,options)=>{
                    const path=new URL(url,document.baseURI).pathname;
                    if(path==='/api/labels'||path==='/api/labels/save'){
                      const value=await crimeLabelApi(path,options?.body?JSON.parse(options.body):null);
                      const response=await original(url,options);response.json=async()=>value;return response;
                    }
                    return original(url,options);
                  };
                  for(const info of Object.values(state.config.datasets)){info.scopes=[];info.crime=true;}
                  state.labels=await api('/api/labels');
                  state.store.mine.crime={crimes:[{key:'CRIME_FIXTURE',severity:'Low',...fields}]};
                  state.store.vanilla.crime=structuredClone(state.store.mine.crime);
                  state.config.datasets.crimeTweaks={readonly:true,crime:true,scopes:[]};state.store.crimeTweaks={crime:{crimes:[]}};
                  state.tab='crime';state.filters.crimeSection='crimes';state.filters.crimeSelected='CRIME_FIXTURE';
                  window.__originalCrime=JSON.stringify(state.store.mine.crime);await renderCrime();
                }''', CRIME_FIELDS)
                cell = page.locator('.crime-table [data-key="CRIME_FIXTURE"] [data-column-key="name"]')
                # The shared panel promotes its Name field into the heading.
                heading = page.locator('#main .lex-detail-panel-heading .human-name')
                page.locator('#main .lex-detail-panel-name').dblclick()
                editor = page.get_by_role('textbox', name='Rename this record', exact=True)
                expect(editor).to_have_value('CRIME_FIXTURE')
                editor.fill('Initial label');editor.press('Enter')
                expect(heading).to_have_value('Initial label')
                cell.dblclick()
                expect(cell.locator('input')).to_have_value('Initial label')
                cell.locator('input').fill('Table label');cell.locator('input').press('Enter')
                expect(heading).to_have_value('Table label')
                heading.fill('Heading label');heading.press('Tab')
                expect(cell.locator('strong')).to_have_text('Heading label');expect(heading).to_have_value('Heading label')
                page.evaluate("async()=>{state.labels={};state.labels=await api('/api/labels');await renderCrime()}")
                expect(heading).to_have_value('Heading label')
                assert json.loads(labels.read_text())['crimes'] == {'CRIME_FIXTURE': 'Heading label', 'CRIME_OTHER': 'Other label'}
                assert page.evaluate('JSON.stringify(state.store.mine.crime)===window.__originalCrime')
                assert page.evaluate('Object.keys(state.crimeEdits).length') == 0
                heading.fill('');heading.press('Tab')
                expect(page.locator('#main .human-name')).to_have_value('')
                expect(page.locator('#main .lex-detail-panel-name')).to_have_text('CRIME_FIXTURE')
                expect(cell.locator('strong')).to_have_text('CRIME_FIXTURE')
                assert json.loads(labels.read_text())['crimes'] == {'CRIME_OTHER': 'Other label'}
                page.screenshot(path=str(tmp_path / 'crime-name-controls.png'), full_page=True)
                assert not errors, errors
            finally:
                browser.close()
    finally:
        http.shutdown();http.server_close();worker.join()


def test_crime_detail_drafts_exact_money_and_readonly(tmp_path):
    with sync_playwright() as play:
        browser=play.chromium.launch(headless=True)
        try:
            page=browser.new_page(viewport={'width':1400,'height':1100})
            errors=[]
            dialogs=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            def dismiss(dialog):dialogs.append(dialog.message);dialog.dismiss()
            page.on('dialog',dismiss)
            page.route('**/*',lambda route:route.abort())
            page.set_content(document().replace('<head>','<head><base href="https://lexeditor.test/">',1))
            page.wait_for_function('!state.booting&&state.catalog?.items?.length')
            page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')")
            page.evaluate('''async fields=>{
              for(const info of Object.values(state.config.datasets)){info.scopes=[];info.crime=true;}
              state.config.datasets.crimeTweaks={readonly:true,crime:true,scopes:[]};
              window.crimeFixture={key:'CRIME_FIXTURE',severity:'Low',...fields};
              state.store.mine.crime={crimes:[crimeFixture,{...crimeFixture,key:'CRIME_OTHER'}]};
              state.store.vanilla.crime={crimes:[{...crimeFixture,CrimeValue:'1000'}]};
              state.store.crimeTweaks={crime:{crimes:[]}};
              state.tab='crime';state.filters.crimeSection='crimes';state.filters.crimeSelected='CRIME_FIXTURE';
              window.__responses['/api/crime/save']={saved:1};await renderCrime();
            }''',CRIME_FIELDS)
            assert page.locator('.crime-table input,.crime-table select').count()==0
            def numeric(label):return page.get_by_role('spinbutton',name='CRIME_FIXTURE '+label,exact=True)
            for label,raw in [('Bounty $',''),('Bounty $','1.001'),('Bounty $','-1'),('Witnesses','1.5'),('Timeout','')]:
                control=numeric(label)
                control.fill(raw)
                assert not control.evaluate('e=>e.checkValidity()'),{'value':control.input_value(),'drafts':page.evaluate('state.crimeEdits'),'errors':errors,'dialogs':dialogs}
                page.evaluate('renderCrime()')
                expect(numeric(label)).to_have_value(raw)
                before=page.evaluate('window.__requests.length')
                assert page.evaluate("async()=>{try{await saveCrime();return ''}catch(e){return e.message}}")
                assert page.evaluate('window.__requests.length')==before
                page.evaluate('state.crimeEdits={};renderCrime()')
            numeric('Bounty $').fill('90071992547409.93')
            numeric('Timeout').fill('0.123456789')
            numeric('Witnesses').fill('3')
            page.evaluate('renderCrime()')
            expect(numeric('Bounty $')).to_have_value('90071992547409.93')
            expect(numeric('Timeout')).to_have_value('0.123456789')
            page.evaluate('saveCrime()')
            edits=page.evaluate("window.__requests.find(r=>r.path==='/api/crime/save').body.edits")
            assert {e['field']:e['value'] for e in edits}=={'CrimeValue':'9007199254740993','Timeout':'0.123456789','NumWitnesses':'3'}
            page.wait_for_function('Object.keys(state.crimeEdits).length===0')
            expect(numeric('Bounty $')).to_have_value('90071992547409.93')
            numeric('Bounty $').focus()
            numeric('Bounty $').locator('..').locator('.lex-reference-value').click()
            expect(numeric('Bounty $')).to_have_value('10.00')
            assert page.evaluate("state.crimeEdits['CRIME_FIXTURE|CrimeValue']")=='10.00'
            page.evaluate("async()=>{state.crimeEdits={};crimeFixture.readonlyFields=['CrimeValue','Disabled','severity'];await renderCrime()}")
            expect(numeric('Bounty $')).to_be_disabled()
            assert not errors,errors
            assert not dialogs,dialogs
            expect(page.get_by_role('checkbox',name='CRIME_FIXTURE Off',exact=True)).to_be_disabled()
            expect(page.get_by_role('combobox',name='CRIME_FIXTURE severity',exact=True)).to_be_disabled()
            assert numeric('Bounty $').locator('..').locator('.lex-reference-value').evaluate_all('es=>es.every(e=>e.disabled)')
            page.evaluate("async()=>{crimeFixture.CrimeValue='NaN';crimeFixture.Disabled='unknown';crimeFixture.severity='UNKNOWN';await renderCrime()}")
            for label,value in [('Bounty $','NaN'),('Off','unknown'),('severity','UNKNOWN')]:
                control=page.get_by_role('textbox',name='CRIME_FIXTURE '+label,exact=True)
                expect(control).to_have_value(value);expect(control).to_be_disabled()
            page.screenshot(path=str(tmp_path/'readonly-crime.png'),full_page=True)
            page.evaluate("async()=>{state.ds='vanilla';await renderCrime()}")
            expect(numeric('Bounty $')).to_be_disabled()
        finally:browser.close()
