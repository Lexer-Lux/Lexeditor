"""Installed battle stages load textures and reset to a useful overview."""
from pathlib import Path
import sys
import tempfile
import os

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plugins.ff8.plugin import FF8Session
from playwright.sync_api import sync_playwright


def main():
    with tempfile.TemporaryDirectory(prefix='lexeditor-stage-') as project:
        with FF8Session({'LEXEDITOR_FF8_PROJECT': project}) as session, sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1600, 'height': 950})
            errors, failed_textures = [], []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('response', lambda response: failed_textures.append(response.url)
                    if any(path in response.url for path in ('/assets/texture.png?', '/assets/summon-texture.png?')) and response.status >= 400 else None)
            page.goto(session.url)
            page.wait_for_function("typeof state!=='undefined'&&!state.booting", timeout=90000)
            page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')", timeout=30000)
            page.evaluate("state.selected.models='a0stg000.x';navigate('models')")
            page.wait_for_function("document.querySelector('.lex-detail-panel-icon img')?.src.startsWith('data:')", timeout=60000)
            page.locator('.lex-detail-panel-icon').click()
            page.wait_for_function("document.querySelector('.lex-model-stage')?.dataset.texturesReady==='true'", timeout=60000)
            stage = page.locator('.lex-model-stage')
            canvas = stage.locator('canvas')
            assert stage.get_attribute('data-rotation') == '0.6,-0.6'
            canvas.press('ArrowRight')
            assert stage.get_attribute('data-rotation') != '0.6,-0.6'
            canvas.press('Home')
            assert stage.get_attribute('data-rotation') == '0.6,-0.6'
            assert page.get_by_role('button', name='Export GLB', exact=True).count() == 0
            page.evaluate("state.selected.models='mag163_a.dat';navigate('models')")
            page.wait_for_function("document.querySelector('.lex-detail-panel-icon img')?.naturalWidth>0", timeout=30000)
            page.get_by_role('combobox', name='Battle texture mag163_a.dat texture 1 palette', exact=True).select_option('1')
            page.wait_for_function("Array.from(document.querySelectorAll('img')).some(i=>i.src.includes('palette=1')&&i.naturalWidth>0)")
            assert page.locator('.lex-model-stage').count() == 0
            page.evaluate("state.selected.models='mag200_b.03';navigate('models')")
            page.locator('[data-lex-layout-section="RESOURCES"]').wait_for(state='visible')
            assert page.locator('.ff8-model-sections').get_by_text('Texture 13', exact=True).is_visible()
            assert page.locator('.lex-model-stage').count() == 0
            page.wait_for_function("Array.from(document.images).some(i=>i.src.includes('/assets/summon-texture.png?')&&i.naturalWidth===128&&i.naturalHeight===256)")
            palette = page.get_by_role('combobox', name='mag200_b.03 texture 13 preview palette', exact=True)
            assert palette.input_value() == '13:0'
            palette.select_option('8:0')
            page.wait_for_function("Array.from(document.images).some(i=>i.src.includes('palette=8%3A0')&&i.complete&&i.naturalWidth===128)")
            palette.select_option('13:0')
            page.wait_for_function("Array.from(document.images).some(i=>i.src.includes('palette=13%3A0')&&i.complete&&i.naturalWidth===128)")
            page.evaluate("state.selected.models='mag200_b.02';navigate('models')")
            page.get_by_role('combobox', name='mag200_b.02 texture 40 preview palette', exact=True).wait_for(state='visible')
            page.wait_for_function("Array.from(document.images).some(i=>i.src.includes('file=mag200_b.02')&&i.complete&&i.naturalWidth===256&&i.naturalHeight===256)")
            assert page.get_by_role('combobox', name='mag200_b.02 texture 40 preview palette', exact=True).input_value() == '21:0'
            page.wait_for_function("document.querySelector('.lex-detail-panel-icon img')?.naturalWidth===256")
            if os.environ.get('LEXEDITOR_RESOURCE_SCREENSHOT'):
                page.mouse.move(10, 10)
                page.screenshot(path=os.environ['LEXEDITOR_RESOURCE_SCREENSHOT'])
            page.evaluate("state.selected.models='mag005_b.05';navigate('models')")
            page.wait_for_function("document.querySelector('.lex-detail-panel-icon img')?.src.startsWith('data:')", timeout=60000)
            page.locator('.lex-detail-panel-icon').click()
            page.wait_for_function("document.querySelector('.lex-model-stage')?.dataset.rendered==='true'", timeout=30000)
            with page.expect_response(lambda response: '/api/model-scene?' in response.url and 'object=8' in response.url) as selected:
                page.get_by_role('combobox', name='Summon mesh object', exact=True).select_option('8')
            assert selected.value.json()['objectId'] == 8
            assert selected.value.json()['textureImages']
            assert selected.value.json()['previewTick'] == 255
            page.wait_for_function("document.querySelector('.lex-model-stage')?.dataset.rendered==='true'", timeout=30000)
            assert not failed_textures, failed_textures
            page.evaluate("state.selected.models='mag184_e.dat';navigate('models')")
            page.wait_for_function("document.querySelector('.lex-detail-panel-icon img')?.src.startsWith('data:')", timeout=60000)
            page.locator('.lex-detail-panel-icon').click()
            page.wait_for_function("document.querySelector('.lex-model-stage')?.dataset.texturesReady==='true'", timeout=30000)
            assert page.get_by_role('button', name='Export GLB', exact=True).is_visible()
            assert not page.locator('.lex-model-stage').get_attribute('data-error')
            if os.environ.get('LEXEDITOR_EFFECT_MODEL_SCREENSHOT'):
                page.mouse.move(10, 10)
                page.screenshot(path=os.environ['LEXEDITOR_EFFECT_MODEL_SCREENSHOT'])
            assert not errors, errors
            browser.close()
    print('Stage preview loads its palette textures; rotation and Home restore the overview.')


if __name__ == '__main__':
    main()
