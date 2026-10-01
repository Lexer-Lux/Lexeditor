"""Installed battle stages load textures and reset to a useful overview."""
from pathlib import Path
import sys
import tempfile

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
                    if '/assets/texture.png?' in response.url and response.status >= 400 else None)
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
            assert not failed_textures, failed_textures
            assert not errors, errors
            browser.close()
    print('Stage preview loads its palette textures; rotation and Home restore the overview.')


if __name__ == '__main__':
    main()
