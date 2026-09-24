"""The production Items pane must expose and save its name control."""
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from rdr2_browser_check import document


def test_item_name_heading_is_visible_and_editable():
    with sync_playwright() as play:
        browser=play.chromium.launch(headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1000})
        page.route('**/*',lambda route:route.abort())
        page.set_content(document().replace('<head>','<head><base href="https://lexeditor.test/">',1))
        page.evaluate('LexeditorUI.finishPluginLoading()')
        page.locator('.lex-list-row').filter(has_text='CONSUMABLE_RUM').click()
        page.evaluate("state.catalog.items.find(i=>i.key==='CONSUMABLE_RUM').textures=[{id:'test',dict:'INVENTORY_ITEMS',type:'INVENTORY'}];renderItems()")
        name=page.get_by_role('textbox',name='Item name',exact=True)
        expect(name).to_have_value('Rum')
        expect(name).to_be_visible()
        page.screenshot(path=str(Path(tempfile.gettempdir())/'lex-rdr2-item-name.png'))
        assert name.bounding_box()['height'] >= 24, name.bounding_box()
        name.fill('Renamed Rum')
        name.blur()
        assert page.evaluate('state.localizationEdits.NAME_RUM')=='Renamed Rum'
        page.locator('#global-save').click()
        page.wait_for_function("window.__requests.some(r=>r.path==='/api/localization/save')")
        assert page.evaluate("window.__requests.find(r=>r.path==='/api/localization/save').body")=={'edits':[{'key':'NAME_RUM','value':'Renamed Rum'}]}
        page.wait_for_function('Object.keys(state.localizationEdits).length===0')
        page.evaluate("state.localization.values.NAME_RUM='\\u00a0';renderItems()")
        expect(name).to_have_value('')
        page.screenshot(path=str(Path(tempfile.gettempdir())/'lex-rdr2-missing-name.png'))
        expect(name).to_have_attribute('placeholder','No localized name')
        name.focus()
        name.blur()
        assert page.evaluate('Object.keys(state.localizationEdits)')==[]
        assert page.evaluate('state.localization.values.NAME_RUM')=='\u00a0'
        page.get_by_role('combobox',name='Filter items by source state').select_option('no-name')
        expect(page.locator('.lex-list-row')).to_have_count(1)
        name.fill('Catalogue heading')
        name.blur()
        assert page.evaluate('state.localizationEdits.NAME_RUM')=='Catalogue heading'
        browser.close()
