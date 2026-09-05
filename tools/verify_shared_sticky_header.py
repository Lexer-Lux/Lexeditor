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
   c.call('Page.addScriptToEvaluateOnNewDocument',{'source':"window.pywebview={api:{transition_snapshot:async()=>({}),lexeditor_settings:async()=>({})}}"})
   c.call('Page.navigate',{'url':session.url+'?lexTransition=resume'})
   wait_eval(c,"typeof state!=='undefined'&&!state.booting",90)
   c.eval("navigate('settings')")
   wait_eval(c,"document.querySelector('.settings-layout input[type=checkbox]')!==null",30)
   assert c.eval("document.querySelector('#toolbar').childElementCount===0&&getComputedStyle(document.querySelector('#toolbar')).display==='none'&&!document.querySelector('#main .lex-settings-save-control')")
   wait_eval(c,"document.querySelector('.lex-plugin-transition-surface.settled')!==null",15)
   for offset in (600,3000):
    c.eval(f"window.scrollTo(0,{offset})")
    c.eval('new Promise(r=>requestAnimationFrame(r))',await_promise=True)
    result=c.eval("({scroll:scrollY,top:document.querySelector('.lex-shell-header').getBoundingClientRect().top,nav:document.querySelector('.lex-shell-header nav').getBoundingClientRect().bottom})")
    assert result['scroll']>0 and abs(result['top'])<1 and result['nav']<900,result
   screenshot(c,'shared-header-scrolled.png')
   print('PASS: shared header and tabs stay visible after transition at scroll 600 and 3000')

finally:
 if p:close_browser(p,b,c)
