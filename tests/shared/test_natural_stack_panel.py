"""Natural stacks in a short detail pane must not overlap following sections."""
from test_shared_ui_feedback import page, framework
import os
from pathlib import Path


def test_natural_stack_keeps_content_height_in_scrollable_panel(page):
    framework(page)
    page.evaluate('''()=>{
      const U=LexeditorUI;
      const rows=Array.from({length:8},(_,i)=>U.detailField({label:'Row '+i,
        control:U.el('input',{type:'number',value:i,min:0,max:99})}));
      const panel=U.detailPanel({title:'Records',body:[U.stack({fill:false},...rows),
        U.detailSection({title:'Following section',body:[U.detailText('Still accessible')]})]});
      panel.style.cssText='height:240px;width:450px;flex:none';
      document.querySelector('main').append(panel);
    }''')
    panel=page.locator('.lex-detail-panel')
    page.wait_for_timeout(100)
    bounds=panel.evaluate('''p=>{
      const stack=p.querySelector('.lex-stack-natural'),last=stack.lastElementChild;
      const next=stack.nextElementSibling;
      return {last:last.getBoundingClientRect().bottom,next:next.getBoundingClientRect().top,
        scroll:p.scrollHeight,client:p.clientHeight};
    }''')
    assert bounds['last']<=bounds['next'], bounds
    assert bounds['scroll']>bounds['client'], bounds
    page.get_by_text('Still accessible',exact=True).scroll_into_view_if_needed()
    assert page.get_by_text('Still accessible',exact=True).is_visible()
    if os.environ.get('LEXEDITOR_TEST_SHOTS'):
        page.screenshot(path=str(Path(os.environ['LEXEDITOR_TEST_SHOTS'])/'natural-stack-panel.png'))
