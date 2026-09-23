"""Check installed tweak definitions in an isolated, headless editor."""
import json
import shutil
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from plugins.rdr2.plugin import Rdr2Session
from playwright.sync_api import sync_playwright

with tempfile.TemporaryDirectory(prefix='lex-tweak-fit-') as folder:
    root=Path(folder)
    ini=root/'GameplayTweaks.ini'
    shutil.copy2('C:/RDR2Mod/GameplayTweaks/GameplayTweaks.ini',ini)
    with Rdr2Session({'LEXEDITOR_GAMEPLAY_INI':str(ini),'RDR2_GAME_ROOT':str(root/'game')}) as session, sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        page=browser.new_page(viewport={'width':2048,'height':1080})
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(session.url)
        page.wait_for_function("typeof state!=='undefined'&&!state.booting",timeout=60000)
        page.evaluate("navigate('settings')")
        page.wait_for_selector('.lex-settings-columns')
        page.wait_for_timeout(500)
        print(json.dumps({'fitErrors':errors},indent=2))
        browser.close()
        assert not errors,errors
