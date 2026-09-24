"""GF and Characters navigation uses a compact, stable portrait strip."""
import os
import tempfile
from pathlib import Path
import pytest
from test_shared_ui_feedback import ROOT, page, framework


@pytest.mark.parametrize('view,count',[('gfs',16),('characters',11)])
def test_portrait_strip(page,view,count):
    assets=ROOT / 'plugins/ff8'
    generated=Path(os.environ['LOCALAPPDATA'])/'Lexeditor/game-data/ff8/generated'
    if not (generated/'portraits'/f'{view}-0.png').is_file():
        pytest.skip('Requires locally extracted FF8 portraits')
    page.route('**/assets/portraits/**',lambda r:r.fulfill(path=str(generated/'portraits'/(r.request.url.split('/')[-2]+'-'+r.request.url.split('/')[-1]))))
    page.route('**/assets/ff8-menu.ttf*',lambda r:r.fulfill(path=str(generated/'ff8-menu.ttf')))
    page.route('**/assets/icons/0.png',lambda r:r.fulfill(path=str(generated/'icons/0.png')))
    framework(page)
    page.add_style_tag(path=str(assets/'editor.css'))
    source=(assets/'records.js').read_text(encoding='utf-8')
    fn=source[source.index('  function portraitTabs('):]
    page.add_script_tag(content='''const {el,subtabBar,recordId}=LexeditorUI;
      const state={vanilla:{},activeSource:'mine'};
      function rowOf(){return null}function referenceValues(){return []}
    '''+fn)
    page.evaluate('''({view,count})=>{
      document.body.dataset.lexPlugin='ff8';
      const toolbar=document.createElement('div');toolbar.id='toolbar';
      document.querySelector('main').before(toolbar);
      const rows=Array.from({length:count},(_,id)=>({id,name:`Portrait ${String(id).padStart(2,'0')}`,fields:[]}));
      window.draw=id=>toolbar.replaceChildren(portraitTabs(view,rows,id,'detail',draw));draw(0);
    }''',dict(view=view,count=count))
    for width in [700,1500,2560]:
        page.set_viewport_size(dict(width=width,height=400))
        page.wait_for_timeout(80)
        bar=page.locator('.lex-subtab-bar-images')
        surface=page.locator('.lex-toolbar')
        assert surface.bounding_box()['height']==80
        assert surface.evaluate('n=>getComputedStyle(n).borderTopWidth')=='3px'
        assert surface.evaluate('n=>getComputedStyle(n).boxShadow')!='none'
        assert surface.evaluate('n=>getComputedStyle(n).backgroundColor')!='rgba(0, 0, 0, 0)' or surface.evaluate('n=>getComputedStyle(n).backgroundImage')!='none'
        bounds=bar.bounding_box()
        buttons=bar.locator('button')
        boxes=[button.bounding_box() for button in buttons.all()]
        assert len({round(box['y']) for box in boxes})==1
        assert max(box['width'] for box in boxes)<=43
        assert abs(boxes[0]['x']+boxes[-1]['x']+boxes[-1]['width']-2*bounds['x']-bounds['width'])<2
        assert all(abs(boxes[i+1]['x']-box['x']-box['width']-2)<1 for i,box in enumerate(boxes[:-1]))
        for button in buttons.all():
            image=button.locator('img')
            assert image.evaluate('n=>n.complete&&n.naturalWidth>0')
            assert abs(image.bounding_box()['height']-button.bounding_box()['height'])<1
        buttons.nth(count//2).click()
        assert [button.bounding_box() for button in bar.locator('button').all()]==boxes
        assert bar.locator('.active').evaluate('n=>getComputedStyle(n).boxShadow')=='none'
        assert bar.locator('.active').evaluate("n=>getComputedStyle(n,'::before').backgroundImage.includes('/assets/icons/0.png')")
    page.screenshot(path=str(Path(tempfile.gettempdir())/f'ff8-{view}-portrait-strip.png'))
