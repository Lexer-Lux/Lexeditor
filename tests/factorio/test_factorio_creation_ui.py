"""Create a prototype through shared Add, then save and reopen it."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
import test_factorio


def test_create_recipe_through_shared_add(tmp_path):
    fixture=test_factorio.FactorioEditEndpointTests()
    project=fixture.project(tmp_path)
    stack,url=fixture.serve(project)
    with stack, sync_playwright() as play:
        browser=play.chromium.launch(headless=True)
        try:
            page=browser.new_page(viewport={'width':1400,'height':900})
            page.goto(url)
            page.wait_for_function('!state.booting')
            page.locator('.lex-plugin-loading-screen').wait_for(state='detached')
            page.get_by_role('button',name='Add recipes',exact=True).click()
            page.get_by_label('New prototype name').fill('custom-gear')
            page.get_by_label('Source prototype').select_option('iron-gear-wheel')
            if os.environ.get('LEXEDITOR_TEST_SHOTS'):
                page.screenshot(path=str(Path(os.environ['LEXEDITOR_TEST_SHOTS'])/'factorio-create.png'))
            page.get_by_role('button',name='Create prototype',exact=True).click()
            page.wait_for_function('state.selected.recipes==="custom-gear" && state.config.dirty===1')
            assert not (project/'overrides.json').exists()
            page.locator('#global-save').click()
            page.wait_for_function('state.config.dirty===0')
            saved=json.loads((project/'overrides.json').read_text())
            assert saved['created']['recipes']['custom-gear']=='iron-gear-wheel'
            page.reload()
            page.wait_for_function('state.data.recipes.some(row=>row.name==="custom-gear" && row.created)')
        finally:
            browser.close()
