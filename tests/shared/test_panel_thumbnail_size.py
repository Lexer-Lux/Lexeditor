"""Long record names must not inflate the picture beside them."""
import os
from test_shared_ui_feedback import page, framework, ROOT


def test_thumbnail_size_is_independent_of_wrapped_title(page):
    framework(page)
    page.add_style_tag(path=str(ROOT/'plugins/ff8/editor.css'))
    page.evaluate('''()=>{
      const U=LexeditorUI,main=document.querySelector('main');
      main.style.cssText='display:flex;flex-direction:row;align-items:start;gap:20px;';
      for(const title of ['Texture','A very long texture name with several descriptive words']){
        const panel=U.detailPanel({title,identity:'#12',icon:U.noImage(),body:U.detailText('Texture properties')});
        panel.style.cssText='width:330px;flex:none;';main.append(panel);
      }
    }''')
    page.wait_for_timeout(150)
    sizes=page.locator('.lex-detail-panel-icon').evaluate_all('es=>es.map(e=>{const r=e.getBoundingClientRect();return [r.width,r.height]})')
    assert len(sizes)==2
    assert sizes[0]==sizes[1]
    assert 40<=sizes[0][0]<=80
    assert sizes[0][0]==sizes[0][1]
    if os.environ.get('LEX_THUMB_SCREENSHOT'):
        page.screenshot(path=os.environ['LEX_THUMB_SCREENSHOT'])
