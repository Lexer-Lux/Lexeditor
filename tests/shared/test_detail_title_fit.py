"""A long record name stays inside its header without splitting its words."""
import os
from test_shared_ui_feedback import page, framework, ROOT


def test_record_title_fits_beside_picture_and_id_after_panel_resize(page):
    framework(page)
    page.add_style_tag(path=str(ROOT / 'plugins/ff8/editor.css'))
    page.evaluate('''()=>{
      const U=LexeditorUI;
      document.querySelector('main').append(U.detailPanel({
        title:'Accelerator', identity:'#123', icon:U.noImage(),
        body:U.detailText('Record properties')
      }));
    }''')
    for width in (500, 330, 280, 500):
        page.locator('.lex-detail-panel').evaluate('(e,w)=>e.style.width=w+"px"', width)
        page.wait_for_timeout(180)
        result = page.locator('.lex-detail-panel-name').evaluate('''e=>{
          const range=document.createRange();range.selectNodeContents(e);
          const text=range.getBoundingClientRect(),box=e.getBoundingClientRect();
          const copy=e.parentElement.querySelector('.lex-copy-value').getBoundingClientRect();
          return {width:box.width,text:text.width,right:text.right,copy:copy.left,
            lines:range.getClientRects().length,size:parseFloat(getComputedStyle(e).fontSize)};
        }''')
        assert result['text'] <= result['width'] + 1, result
        assert result['right'] <= result['copy'] + 1, result
        assert result['lines'] == 1, result
        assert result['size'] >= 14, result
    if os.environ.get('LEX_TITLE_SCREENSHOT'):
        page.screenshot(path=os.environ['LEX_TITLE_SCREENSHOT'])
