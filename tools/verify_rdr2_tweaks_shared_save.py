import sys,tempfile,shutil,json,configparser
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from games.rdr2.plugin import Rdr2Session
from tools.verify_panel_layout_visual_46 import browser_session,close_browser,wait_eval,screenshot
p=b=c=None
try:
 with tempfile.TemporaryDirectory(prefix='rdr2-shared-save-') as tmp:
  ini=Path(tmp)/'GameplayTweaks.ini';shutil.copy2('C:/RDR2Mod/GameplayTweaks/GameplayTweaks.ini',ini)
  p,b,c=browser_session()
  with Rdr2Session({'LEXEDITOR_GAMEPLAY_INI':str(ini),'RDR2_GAME_ROOT':str(Path(tmp)/'empty-game-root')}) as session:
   c.call('Page.navigate',{'url':session.url})
   wait_eval(c,"typeof state!=='undefined'&&!state.booting",90)
   c.eval("navigate('settings')")
   wait_eval(c,"document.querySelector('.settings-layout input[type=checkbox]')!==null",30)
   assert c.eval("document.querySelector('#toolbar').childElementCount===0&&getComputedStyle(document.querySelector('#toolbar')).display==='none'&&!document.querySelector('#main .lex-settings-save-control')")
   c.eval("document.querySelector('.settings-layout input[type=checkbox]').click()")
   edits=c.eval('state.settingEdits');assert len(edits)==1,edits
   assert c.eval("!document.querySelector('#global-save').disabled")
   screenshot(c,'rdr2-tweaks-shared-save.png')
   c.eval("document.querySelector('#global-save').click()")
   wait_eval(c,"Object.keys(state.settingEdits).length===0&&document.querySelector('#global-save').disabled",30)
   cfg=configparser.ConfigParser(strict=False);cfg.read(ini)
   for key,value in edits.items():
    section,name=key.split('|',1);assert cfg.get(section,name)==value,(key,value)
   assert not c.eval('window.__testErrors'),c.eval('window.__testErrors')
   print('PASS: no top panel or local Save; main Save persisted the edited tweak to an isolated INI and cleared dirty state')
finally:
 if p:close_browser(p,b,c)
