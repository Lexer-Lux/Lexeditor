"""Hidden RDR editor interaction and complete-row regression checks. No save calls."""
import sys,tempfile,time,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.verify_panel_layout_visual_46 import browser_session,close_browser,screenshot,wait_eval,Rdr2Session
from games.rdr.plugin import RdrSession
BOUNDS="""(()=>{const list=document.querySelector('.effect-column-list,.behavior-column-list,.rdr-record-list');const rows=[...list.querySelectorAll('.effect-column-row,.behavior-column-row,.rdr-record-entry')];const rect=list.getBoundingClientRect();return {rows:rows.length,over:rows.filter(r=>r.getBoundingClientRect().bottom>rect.bottom+1).length,cut:rows.filter(r=>[...r.querySelectorAll('.lex-column-cell-content')].some(x=>x.getBoundingClientRect().bottom>r.getBoundingClientRect().bottom+1||x.scrollHeight>x.clientHeight+1)).length,detailOverflow:[...document.querySelectorAll('.effect-detail')].some(x=>x.scrollWidth>x.clientWidth+1),height:rect.height,scroll:list.scrollHeight>list.clientHeight+1}})()"""
def dimensions(c,w,h):
 c.call('Emulation.setDeviceMetricsOverride',{'width':w,'height':h,'deviceScaleFactor':1,'mobile':False});time.sleep(1)
def check(c,label):
 result=c.eval(BOUNDS);print(label,result,flush=True)
 assert result['rows'] and not result['over'] and not result['cut'] and not result['detailOverflow'] and not result['scroll'],result
 return result['rows']
p,b,c=browser_session()
try:
 with tempfile.TemporaryDirectory() as tmp:
  ini=Path(tmp)/'GameplayTweaks.ini';shutil.copy2(r'C:\RDR2Mod\GameplayTweaks\GameplayTweaks.ini',ini)
  with Rdr2Session({'LEXEDITOR_GAMEPLAY_INI':str(ini),'RDR2_GAME_ROOT':str(Path(tmp)/'empty')}) as s:
   c.call('Page.navigate',{'url':s.url});wait_eval(c,"typeof state!=='undefined'&&!state.booting",90)
   for section in ['effects','behaviors']:
    c.eval(f"state.tab='effects';state.filters.effectSection={json.dumps(section)};render()");time.sleep(1)
    counts=[]
    for width,height in [(1600,900),(1280,720),(1600,900)]:
     dimensions(c,width,height);counts.append(check(c,f'{section}-{width}x{height}'));screenshot(c,f'rdr-editor-{section}-{width}x{height}.png')
    assert counts[0]==counts[2] and counts[1]<counts[0],counts
   c.eval("state.tab='challenges';render()");time.sleep(1)
   assert c.eval("[...document.querySelectorAll('.challenge-rewards')].every(x=>x.querySelector('.multi-ref-add').getBoundingClientRect().top>=x.querySelector('.multi-ref-field').getBoundingClientRect().bottom)")
   # Compare the currently selected source with its baseline; editing must reveal the reference and restoring must hide it.
   c.eval("window.__counter=document.querySelector('.challenge-control-stack select');window.__counterOriginal=__counter.value;__counter.value=[...__counter.options].find(o=>o.value!==__counter.value).value;__counter.dispatchEvent(new Event('change'))")
   assert c.eval("document.querySelector('.challenge-control-stack select').closest('.challenge-control-stack').querySelector('.ref')!==null")
   c.eval("let s=document.querySelector('.challenge-control-stack select');s.value=__counterOriginal;s.dispatchEvent(new Event('change'))")
   assert c.eval("document.querySelector('.challenge-control-stack select').closest('.challenge-control-stack').querySelector('.ref')===null")
   c.eval("state.tab='loot';render()")
   wait_eval(c,"document.querySelector('[title=\"Add a catalog item directly to this table\"]')!==null",60)
   for title,kind in [("Add a catalog item directly to this table","Item"),("Add a reference that rolls another loot table or reusable Item Group","Table")]:
    c.eval("window.__lootTable=Object.values(state.loot).flatMap(x=>x.tables).find(t=>t.key===state.filters.lootSel);window.__entryCount=__lootTable.entries.length")
    c.eval(f"document.querySelector('[title={json.dumps(title)}]').click()")
    assert c.eval("__lootTable.entries.length===__entryCount"), "opening a picker must not add a blank row"
    c.eval("{let q=document.querySelector('#picker input');q.value='NO_MATCH_123456789';q.dispatchEvent(new Event('input'))}")
    assert c.eval("document.querySelectorAll('#picker .picker-option').length===0")
    c.eval("{let q=document.querySelector('#picker input');q.value='';q.dispatchEvent(new Event('input'));window.__picked=document.querySelector('#picker .picker-option').innerText;document.querySelector('#picker .picker-option').click()}")
    assert c.eval(f"__lootTable.entries.length===__entryCount+1 && __lootTable.entries.at(-1).name===__picked && __lootTable.entries.at(-1).type==={json.dumps(kind)}")
   print('Loot item/table picker selection and counter restore passed',flush=True)
  with RdrSession({'LEXEDITOR_RDR_PROJECT':str(Path(tmp)/'rdr')}) as s:
   c.call('Page.navigate',{'url':s.url});wait_eval(c,"typeof state!=='undefined'&&!state.booting",90)
   for tab in ['items','shops','missions']:
    c.eval(f"state.tab={json.dumps(tab)};render()");time.sleep(.5)
    for width,height in [(1600,900),(1280,720)]:
     dimensions(c,width,height);check(c,f'rdr1-{tab}-{width}x{height}')
    if tab=='items':
     assert c.eval("document.querySelectorAll('.item-detail .lex-info-help').length>0 && !document.querySelector('.item-detail').innerText.includes('Only direct scalar')")
   assert not c.eval('window.__testErrors'),c.eval('window.__testErrors')
 print('RDR editor complete-row and interaction checks passed',flush=True)
finally:close_browser(p,b,c)
