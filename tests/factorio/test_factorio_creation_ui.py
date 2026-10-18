"""Create a prototype through shared Add, then save and reopen it."""
import json
import os
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright
import test_factorio


@pytest.mark.parametrize('kind,template', [('items','iron-plate'),('recipes','iron-gear-wheel'),
    ('machines','assembling-machine-1'),('technologies','automation')])
def test_create_each_family_through_shared_add(tmp_path,kind,template):
    fixture=test_factorio.FactorioEditEndpointTests()
    project=fixture.project(tmp_path)
    source=project/'source/data-raw-dump.json'
    original=source.read_bytes()
    name='custom-'+kind
    stack,url=fixture.serve(project)
    with stack, sync_playwright() as play:
        browser=play.chromium.launch(headless=True)
        try:
            page=browser.new_page(viewport={'width':1400,'height':900})
            page.goto(url)
            page.wait_for_function('!state.booting')
            page.locator('.lex-plugin-loading-screen').wait_for(state='detached')
            page.evaluate('kind=>navigate(kind)',kind)
            page.locator('.lex-table-add').click()
            page.get_by_label('New prototype name').fill(name)
            page.get_by_label('Source prototype').select_option(template)
            if os.environ.get('LEXEDITOR_TEST_SHOTS'):
                page.screenshot(path=str(Path(os.environ['LEXEDITOR_TEST_SHOTS'])/f'factorio-create-{kind}.png'))
            page.get_by_role('button',name='Create prototype',exact=True).click()
            page.wait_for_function('({kind,name})=>state.selected[kind]===name && state.config.dirty===1',arg={'kind':kind,'name':name})
            assert not (project/'overrides.json').exists()
            page.locator('#global-save').click()
            page.wait_for_function('state.config.dirty===0')
            saved=json.loads((project/'overrides.json').read_text())
            assert saved['created'][kind][name]==template
            assert source.read_bytes()==original
            page.reload()
            page.wait_for_function('({kind,name})=>state.data[kind].some(row=>row.name===name && row.created)',arg={'kind':kind,'name':name})
            assert source.read_bytes()==original
        finally:
            browser.close()
