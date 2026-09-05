"""Rendered FF8 panel order, selected-record refresh, and readable UI checks."""
import sys,tempfile,time,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.verify_panel_layout_visual_46 import browser_session,close_browser,screenshot,wait_eval,FF8Session
p,b,c=browser_session()
try:
 with tempfile.TemporaryDirectory() as tmp:
  with FF8Session({'LEXEDITOR_FF8_PROJECT':tmp}) as s:
   c.call('Page.navigate',{'url':s.url});wait_eval(c,"typeof state!=='undefined'&&!state.booting",90)
   for tab,secondary in [('magic','.magic-compat-column'),('enemies','.enemy-tabbed-column')]:
    c.eval(f'navigate({json.dumps(tab)})');time.sleep(1)
    for width,height in [(1600,900),(1280,720)]:
     c.call('Emulation.setDeviceMetricsOverride',{'width':width,'height':height,'deviceScaleFactor':1,'mobile':False});time.sleep(.6)
     result=c.eval("""(()=>{const root=document.querySelector('.lex-leading-list-detail'),panes=[...root.children].filter(x=>x.classList.contains('lex-panel-layout-pane')),r=panes.map(x=>x.getBoundingClientRect());return {classes:panes.map(x=>x.className),ordered:r[0].right<=r[1].left&&r[1].right<=r[2].left,bounded:r.every(x=>x.bottom<=document.querySelector('#main').getBoundingClientRect().bottom+1),tabs:[...document.querySelectorAll('nav .lex-tab-label-text')].every(x=>x.scrollWidth<=x.clientWidth+1),badges:[...document.querySelectorAll('nav button')].every(x=>x.querySelectorAll('.lex-tab-shortcut').length<=1),compatCut:[...document.querySelectorAll('.magic-compat-column .lex-column-list-row')].some(x=>x.getBoundingClientRect().bottom>panes[0].getBoundingClientRect().bottom+1)}})()""")
     print(tab,width,result,flush=True);assert result['ordered'] and result['bounded'] and result['tabs'] and result['badges'] and not result['compatCut'],result
     screenshot(c,f'ff8-left-panels-{tab}-{width}.png')
    c.eval("window.__leading=document.querySelector('.lex-leading-list-detail').firstElementChild;window.__selected=state.selected[state.tab];document.querySelectorAll('.lex-barrelled-master .lex-column-list-row:not(.lex-filler-row)')[1].click()")
    time.sleep(.3)
    assert c.eval("state.selected[state.tab]!==__selected && !__leading.isConnected"), 'record selection must refresh the leading panel'
   c.call('Emulation.setDeviceMetricsOverride',{'width':1600,'height':900,'deviceScaleFactor':1,'mobile':False})
   c.eval("navigate('encounters')");time.sleep(1)
   headers=c.eval("""[...document.querySelectorAll('.encounter-slot-table .lex-column-list-head-cell')].filter(x=>/Loaded|Targetable/.test(x.textContent)).map(x=>{const label=x.querySelector('.header-label'),range=document.createRange();range.selectNodeContents(label);const r=range.getBoundingClientRect(),p=x.getBoundingClientRect();return{text:label.textContent,fit:r.left>=p.left&&r.right<=p.right,width:r.width}})""")
   assert len(headers)==2 and all(x['fit'] for x in headers),headers
   c.eval("state.filters.text='Description';navigate('text')");time.sleep(1)
   assert c.eval("document.querySelector('.lex-detail-panel-meta').textContent.trim()==='Description' && !document.querySelector('.lex-detail-panel-title').textContent.includes('Description')")
   assert c.eval("[...document.querySelectorAll('[data-column-key=role] .lex-column-cell-content')].every(x=>x.scrollWidth<=x.clientWidth+1)")
   c.eval("navigate('characters')");time.sleep(.6)
   pos=c.eval("(()=>{let r=document.querySelector('.character-limit-break-field').getBoundingClientRect();return{x:r.left+r.width/2,y:r.top+r.height/2}})()")
   c.call('Input.dispatchMouseEvent',{'type':'mouseMoved',**pos,'button':'none','buttons':0});time.sleep(.3)
   pos=c.eval("(()=>{let r=document.querySelector('.character-limit-break-field .lex-field-type-name').getBoundingClientRect();return{x:r.left+r.width/2,y:r.top+r.height/2}})()")
   c.call('Input.dispatchMouseEvent',{'type':'mouseMoved',**pos,'button':'none','buttons':0});time.sleep(.3)
   assert c.eval("(()=>{const r=document.querySelector('.character-limit-break-field .lex-field-type-rail');return getComputedStyle(r.querySelector('.lex-field-type-name')).opacity==='0'&&getComputedStyle(r.querySelector('.lex-info-help')).opacity==='1'&&r.querySelector('.lex-info-help').textContent.trim()==='?'})()")
   assert not c.eval('window.__testErrors'),c.eval('window.__testErrors')
   print('FF8 original panel and text reports passed',flush=True)
finally:close_browser(p,b,c)
