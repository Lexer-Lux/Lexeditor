"""Installed-model browser check: both callers, rendered geometry and GLB download."""
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from plugins.ff8.plugin import FF8Session
from playwright.sync_api import sync_playwright


def check_card_overlay(page):
    cards=page.locator('.lex-record-card')
    assert cards.count()>0
    for card in cards.all():
        bounds=card.evaluate('''card=>{
            const box=card.getBoundingClientRect(), image=card.querySelector('.lex-record-card-image').getBoundingClientRect();
            const header=card.querySelector('.lex-record-card-header').getBoundingClientRect();
            const body=card.querySelector('.lex-record-card-body')?.getBoundingClientRect();
            return {fills:Math.abs(image.width-card.clientWidth)<2&&Math.abs(image.height-card.clientHeight)<2,
                    header:header.top>=image.top&&header.bottom<=image.bottom,
                    body:!body||(body.top>=image.top&&body.bottom<=image.bottom)};
        }''')
        assert all(bounds.values()),bounds


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
            check_card_overlay(page)
            shots=Path(tempfile.gettempdir())/'lexeditor-dev/rendered'
            shots.mkdir(parents=True,exist_ok=True)
            page.wait_for_timeout(800)
            page.screenshot(path=str(shots/'ff8-texture-card-overlays.png'))
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
            page.locator('.enemy-detail .lex-model-preview-trigger').click()
            thumbnail_requests=[]
            page.on('request',lambda request:thumbnail_requests.append(request.url) if '/api/model-scene?' in request.url else None)
            page.evaluate('''()=>{
                const models=new Set(state.data.models.rows.filter(row=>row.enemyId!=null&&row.vertices>0).map(row=>row.enemyId));
                const formations=new Set(state.data.encounters.rows.filter(row=>
                    row.slots.some(slot=>slot.enabled&&models.has(slot.enemyId))).map(row=>row.id));
                const groups=new Set(state.data.world.rows.filter(row=>row.kind==='group'&&
                    row.encounters.some(id=>formations.has(id))).map(row=>row.id));
                const rules=state.data.world.rows.filter(row=>row.kind==='helper'&&groups.has(row.encounterGroup));
                const rule=rules.find(row=>row.encounterGroup===31)||rules[0];
                if(!rule)throw Error('No world rule uses the model fixture enemy');
                state.selected.encounterRule=rule.id;state.encountersTab='rules';navigate('encounters');
            }''')
            page.wait_for_selector('.ff8-model-thumbnail[data-model-ready="true"]',timeout=60000)
            thumb=page.locator('.ff8-model-thumbnail[data-model-ready="true"]').first
            assert thumb.get_attribute('src').startswith('data:image/png;base64,')
            assert thumb.evaluate('image=>image.complete&&image.naturalWidth>12&&image.naturalHeight>12')
            page.wait_for_function("[...document.querySelectorAll('.ff8-model-thumbnail')].every(image=>image.dataset.modelReady==='true')",timeout=60000)
            assert max(Counter(thumbnail_requests).values()) == 1, thumbnail_requests
            assert page.locator('.lex-model-stage').count() == 0, 'thumbnail renderer was not disposed'
            check_card_overlay(page)
            screenshot=Path(tempfile.gettempdir())/'lexeditor-dev/rendered/ff8-encounter-models.png'
            page.screenshot(path=str(screenshot))
            assert not errors,errors
            page.route('**/api/card-players',lambda route:route.fulfill(json={
                'ready':True,'keys':['card-overlay'],'players':[{'map':'card-overlay','id':0,
                'entity':'Player','script':'talk','deckId':201,'deckMode':'literal'}],'scanned':1,'total':1}))
            page.evaluate('''()=>{
                state.data.fields.rows=[{key:'card-overlay',name:'Card overlay check',_loaded:true,
                    players:[{id:0,entity:'Player',params:[
                        {id:0,name:'Deck ID',mode:'literal',editable:true,value:201},
                        {id:6,name:'Card levels',mode:'literal',editable:true,value:1}]}]}];
                navigate('cards');
            }''')
            page.get_by_role('tab',name='Players',exact=False).click()
            page.wait_for_selector('.lex-record-card',timeout=20000)
            check_card_overlay(page)
            page.wait_for_timeout(300)
            page.screenshot(path=str(shots/'ff8-pool-card-overlays.png'))
            assert not errors,errors
            print(f'Models and Enemies render geometry; {visible} opaque pixels; rotation/zoom/reset, GLB download, encounter thumbnails, request sharing and renderer cleanup passed.')
        finally:
            browser.close()


if __name__=='__main__':main()
