"""Installed-model browser check: both callers, rendered geometry and GLB download."""
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from plugins.ff8.plugin import FF8Session
from playwright.sync_api import sync_playwright


def main():
    with tempfile.TemporaryDirectory(prefix='ff8-model-viewer-') as project, FF8Session({'LEXEDITOR_FF8_PROJECT':project}) as session, sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        try:
            page=browser.new_page(viewport={'width':1600,'height':1000})
            errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(session.url)
            page.wait_for_function("typeof state!=='undefined'&&!state.booting",timeout=120000)
            enemy=page.evaluate("()=>{const row=state.data.models.rows.find(row=>row.file==='c0m001.dat');state.selected.models=row.file;navigate('models');return row.enemyId}")
            assert page.locator('.lex-detail-panel-icon .lex-no-image').count()==1
            trigger=page.locator('.lex-model-preview-trigger').first
            trigger.click()
            stage=page.locator('.lex-model-stage')
            page.wait_for_function("document.querySelector('.lex-model-stage')?.dataset.texturesReady==='true'",timeout=30000)
            assert not stage.get_attribute('data-error')
            visible=stage.locator('canvas').evaluate('''canvas=>{const gl=canvas.getContext('webgl'),data=new Uint8Array(canvas.width*canvas.height*4);gl.readPixels(0,0,canvas.width,canvas.height,gl.RGBA,gl.UNSIGNED_BYTE,data);let count=0;for(let index=3;index<data.length;index+=4)if(data[index])count++;return count}''')
            screenshot=Path(tempfile.gettempdir())/'lexeditor-dev/rendered/ff8-model-3d.png'
            screenshot.parent.mkdir(parents=True,exist_ok=True)
            page.screenshot(path=str(screenshot))
            assert visible>1000,(visible,stage.bounding_box(),stage.locator('canvas').evaluate('n=>[n.width,n.height,n.getBoundingClientRect().toJSON()]'))
            canvas=stage.locator('canvas')
            canvas.focus();canvas.press('ArrowRight')
            assert stage.get_attribute('data-rotation').startswith('0.1,')
            canvas.press('+');assert float(stage.get_attribute('data-zoom'))>.9
            canvas.press('Home');assert stage.get_attribute('data-rotation')=='0,0'
            screenshot=Path(tempfile.gettempdir())/'lexeditor-dev/rendered/ff8-model-3d.png'
            screenshot.parent.mkdir(parents=True,exist_ok=True)
            page.screenshot(path=str(screenshot))
            with page.expect_download() as download:
                page.get_by_role('button',name='Export GLB',exact=True).click()
            exported=Path(project)/'preview.glb'
            download.value.save_as(exported)
            assert exported.read_bytes().startswith(b'glTF')
            trigger.click();page.wait_for_timeout(250)
            assert stage.count()==0
            page.evaluate('(id)=>{state.selected.enemies=id;navigate("enemies")}',enemy)
            page.locator('.enemy-detail .lex-model-preview-trigger').click()
            page.wait_for_function("document.querySelector('.lex-model-stage')?.dataset.texturesReady==='true'",timeout=30000)
            assert page.locator('.lex-model-stage').get_attribute('data-rendered')=='true'
            assert not errors,errors
            print(f'Models and Enemies render geometry; {visible} opaque pixels; rotation/zoom/reset, GLB download and close cleanup passed.')
        finally:
            browser.close()


if __name__=='__main__':main()
