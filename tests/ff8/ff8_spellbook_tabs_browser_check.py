"""Spellbook stays inside the abilities panel and preserves tab content."""
import json,re,tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from plugin_ui import plugin_ui
def main():
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True);page=browser.new_page()
  page.route('http://fixture/',lambda r:r.fulfill(body='<div id="gf-detail" data-gf="10" style="width:650px;height:600px"><section class="gf-panel abilities" data-gf-panel="abilities"><h3 class="lex-detail-section-title">ABILITIES</h3><div class="lex-detail-section-content"><input aria-label="Native ability" value="21"></div></section></div>',content_type='text/html'))
  page.route('**/api/kernel?*',lambda r:r.fulfill(body=json.dumps({'rows':[{'id':10,'spellbook':None}],'spellbook':{'enabled':True,'magicOptions':[{'id':1,'name':'Fire'}],'abilityOptions':[]}}),content_type='application/json'))
  page.goto('http://fixture/')
  page.add_style_tag(content=(ROOT/'ui/framework.css').read_text(encoding='utf-8'))
  page.add_style_tag(content=(ROOT/'plugins/ff8/editor.css').read_text(encoding='utf-8'))
  page.add_script_tag(content=(ROOT/'ui/framework.js').read_text(encoding='utf-8'))
  # The GF page gives its detail host a way to swap one of its panels; the
  # spellbook uses it to put the abilities panel inside its tabs.
  page.evaluate("()=>{document.querySelector('#gf-detail').lexReplacePanel=(old,next)=>old.replaceWith(next)}")
  page.evaluate('''()=>{
    const content=document.querySelector('.lex-detail-section-content');
    const input=content.querySelector('input');
    content.replaceChildren(LexeditorUI.columnList({rows:Array.from({length:22},(_,id)=>({id})),
      columns:[{key:'id',label:'Slot',render:r=>r.id},{key:'ability',label:'Ability',render:r=>r.id===0?input:
        LexeditorUI.inlineLabel(LexeditorUI.inlineLabel(LexeditorUI.el('img',{
          src:'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"><path fill="%23998ab6" d="M2 2h12v12H2z"/></svg>',alt:''})),
          LexeditorUI.el('span',{},'Ability '+r.id))}]}));
  }''')
  page.add_style_tag(content='#gf-detail {display:flex} #gf-detail > .lex-tabbed-panel {flex:1;min-height:0}')
  page.add_script_tag(content=(ROOT/'plugins/ff8/cards_ui.js').read_text(encoding='utf-8'))
  page.get_by_role('tab',name='SPELLBOOK').wait_for()
  # The abilities panel is replaced by one tabbed panel holding both views.
  assert page.locator('.lex-tabbed-panel .lexeditor-gf-spellbook').count()==1
  assert page.get_by_label('Native ability').is_visible()
  table=page.locator('.lex-tabbed-panel-content > .lex-column-list')
  table_box=table.bounding_box()
  content_box=page.locator('.lex-tabbed-panel-content').bounding_box()
  for key in ('x','y','width','height'):
    assert abs(table_box[key]-content_box[key])<2,(table_box,content_box)
  icons=table.locator('.lex-inline-label > img')
  page.locator('#gf-detail').evaluate('n=>n.style.height="1100px"')
  table.evaluate('n=>n.style.gridTemplateRows="40px repeat(22,48px)"')
  page.wait_for_timeout(150)
  assert icons.count()==21
  for icon in icons.all():
    assert icon.evaluate('''n=>{
      const r=n.getBoundingClientRect(),p=n.parentElement.getBoundingClientRect();
      const font=parseFloat(getComputedStyle(n).fontSize);
      return r.height>5 && r.width>5 && r.height<=font*1.36 && r.width<=font*1.36 &&
        r.left>=p.left-1 && r.right<=p.right+1 && r.top>=p.top-1 && r.bottom<=p.bottom+1;
    }'''),icon.bounding_box()
  page.screenshot(path=str(Path(tempfile.gettempdir())/'lex-gf-abilities-table.png'))
  page.get_by_role('tab',name='SPELLBOOK').click()
  page.get_by_role('button',name='ADD PAGE').wait_for(state='visible')
  assert not page.get_by_label('Native ability').is_visible()
  page.get_by_role('button',name='ADD PAGE').click()
  page.get_by_role('tab',name='ABILITIES',exact=True).click()
  assert page.get_by_label('Native ability').input_value()=='21'
  assert not page.locator('.lexeditor-gf-spellbook').is_visible()
  page.get_by_role('tab',name='SPELLBOOK').click()
  assert page.get_by_role('button',name='ADD PAGE').count()==1
  page.get_by_role('button',name='ADD SPELL',exact=True).click()
  assert page.locator('.lexeditor-gf-spellbook .lex-column-list-row').count()==1
  assert page.evaluate('window.ff8SpellbookDrafts.size')==1
  assert page.evaluate('''()=>{
    const event=new Event('beforeunload',{cancelable:true});
    window.dispatchEvent(event);return event.defaultPrevented;
  }''') is False
  assert page.locator('[role="tab"] .lex-info-help').count()==1
  page.screenshot(path=str(Path(tempfile.gettempdir())/'lex-spellbook-list.png'))
  dialogs=[]
  page.on('dialog',lambda dialog:(dialogs.append(dialog.type),dialog.dismiss()))
  page.goto('about:blank')
  assert dialogs==[],dialogs
  browser.close()
 print('Spellbook tab containment, tab switching and independent ability value passed.')
if __name__=='__main__':main()
