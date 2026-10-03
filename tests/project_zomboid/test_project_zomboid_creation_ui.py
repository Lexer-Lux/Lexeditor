"""Shared Add creates a real script record and reloads it in the structured view."""
import os
from pathlib import Path
import threading
import pytest

from playwright.sync_api import TimeoutError as BrowserTimeout, sync_playwright
from plugins.project_zomboid import server, zedscript
from verify_project_zomboid_ui import write_fixture


CREATION_VIEWS = [
    ('animationsMesh', 'animationmeshes'), ('item', 'items'), ('evolvedrecipe', 'evolved'),
    ('craftRecipe', 'crafts'), ('fixing', 'fixing'), ('fluid', 'fluids'),
    ('vehicle', 'vehicles'), ('sound', 'sounds'), ('model', 'models'),
    ('mannequin', 'mannequins'), ('timedAction', 'timedactions'),
]


@pytest.mark.parametrize('kind,tab', CREATION_VIEWS)
def test_create_each_supported_family_through_shared_add(tmp_path,monkeypatch,kind,tab):
    assert {family for family, _ in CREATION_VIEWS} == zedscript._EDITABLE
    project=tmp_path/'Fixture'
    write_fixture(project)
    monkeypatch.setenv('LEXEDITOR_PROJECT_ZOMBOID_PROJECT',str(project))
    monkeypatch.setenv('LEXEDITOR_PROJECT_ZOMBOID_USER_ROOT',str(tmp_path/'user'))
    monkeypatch.setenv('LEXEDITOR_MOD_READ_ONLY','0')
    monkeypatch.setenv('LEXEDITOR_NO_MOD','0')
    service=server.create_server(0)
    thread=threading.Thread(target=service.serve_forever,daemon=True)
    thread.start()
    try:
        with sync_playwright() as play:
            browser=play.chromium.launch(headless=True)
            try:
                page=browser.new_page(viewport={'width':1500,'height':950})
                startup_errors=[]
                page.on('pageerror',lambda error:startup_errors.append(f'JavaScript: {error}'))
                page.on('requestfailed',lambda request:startup_errors.append(
                    f'Network: {request.url}: {request.failure}'))
                page.on('response',lambda response:startup_errors.append(
                    f'HTTP: {response.status} {response.url}')
                    if '/api/' in response.url and response.status>=400 else None)
                page.goto(f'http://127.0.0.1:{service.server_port}')
                try:
                    page.wait_for_function('items.rows.length>0 || !!document.querySelector(".pz-error-message")')
                except BrowserTimeout:
                    pytest.fail(f'Project Zomboid startup timed out: {startup_errors}; '
                                f'page: {page.locator("body").inner_text()}')
                assert page.evaluate('items.rows.length>0'), (
                    startup_errors, page.locator('.pz-error-message').all_text_contents())
                page.locator('.lex-plugin-loading-screen').wait_for(state='detached')
                name='Created'+kind
                original=next(row for row in zedscript.inventory(project)['rows'] if row['kind']==kind)
                source=project/original['path']
                before=source.read_bytes().decode('utf-8-sig')
                template=before[original['start']:original['end']]
                assert template.startswith(kind)
                page.evaluate('tab=>navigate(tab)',tab)
                page.locator('.lex-table-add').click()
                # Copy the selected family's fixture rather than assuming list order.
                templates=page.get_by_label('Copy from record')
                option=templates.locator('option').evaluate_all('''(options,name)=>options.find(n=>n.textContent.includes(name))?.value''',
                    f".{original['name']} ({kind})")
                assert option is not None
                templates.select_option(option)
                page.get_by_label('New record name').fill(name)
                assert page.get_by_label('New record name').evaluate('''input=>{
                    const field=input.closest('.lex-detail-field');
                    return getComputedStyle(field).gridTemplateColumns.split(' ').length>=2;
                }''')
                if os.environ.get('LEXEDITOR_TEST_SHOTS'):
                    page.screenshot(path=str(Path(os.environ['LEXEDITOR_TEST_SHOTS'])/f'pz-create-{kind}.png'))
                page.get_by_role('button',name='Create record',exact=True).click()
                page.wait_for_function('name=>scripts.rows.some(row=>row.name===name)',arg=name)
                assert any(row['name']==name and row['kind']==kind for row in zedscript.inventory(project)['rows'])
                assert source.read_bytes().decode('utf-8-sig')[original['start']:original['end']]==template
                page.reload()
                page.wait_for_function('name=>scripts.rows.some(row=>row.name===name)',arg=name)
                page.evaluate('tab=>navigate(tab)',tab)
                assert page.locator('.pz-record-table').get_by_text(name,exact=True).count()==1
            finally:
                browser.close()
    finally:
        service.shutdown()
        thread.join(timeout=5)
        service.server_close()
