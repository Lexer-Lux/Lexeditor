"""Shared Add creates a real script record and reloads it in the structured view."""
import os
from pathlib import Path
import threading

from playwright.sync_api import sync_playwright
from plugins.project_zomboid import server, zedscript
from verify_project_zomboid_ui import write_fixture


def test_create_item_through_shared_add(tmp_path,monkeypatch):
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
                page.goto(f'http://127.0.0.1:{service.server_port}')
                page.wait_for_function('items.rows.length>0')
                page.locator('.lex-plugin-loading-screen').wait_for(state='detached')
                page.evaluate('navigate("items")')
                page.get_by_role('button',name='Add items',exact=True).click()
                page.get_by_label('New record name').fill('CreatedItem')
                assert page.get_by_label('New record name').evaluate('''input=>{
                    const field=input.closest('.lex-detail-field');
                    return getComputedStyle(field).gridTemplateColumns.split(' ').length>=2;
                }''')
                if os.environ.get('LEXEDITOR_TEST_SHOTS'):
                    page.screenshot(path=str(Path(os.environ['LEXEDITOR_TEST_SHOTS'])/'pz-create.png'))
                page.get_by_role('button',name='Create record',exact=True).click()
                page.wait_for_function('items.rows.some(row=>row.id==="CreatedItem")')
                assert any(row['name']=='CreatedItem' for row in zedscript.inventory(project)['rows'])
                page.reload()
                page.wait_for_function('items.rows.some(row=>row.id==="CreatedItem")')
            finally:
                browser.close()
    finally:
        service.shutdown()
        thread.join(timeout=5)
        service.server_close()
