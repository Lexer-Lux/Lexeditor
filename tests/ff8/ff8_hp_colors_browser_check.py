"""Render schema-backed HP Colors and independent mod states without saving."""
import json,sys,threading,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from plugins.ff8.server import create_server
from playwright.sync_api import sync_playwright
from test_ff8_hp_colors_issue_481 import HELP
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'shared'))
from paged_detail import reveal
server=create_server(0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
try:
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={"width":1280,"height":900})
        errors=[];writes=[];page.on("pageerror",lambda error:errors.append(str(error)))
        def route_api(route):
            if route.request.method!="GET":writes.append((route.request.method,route.request.url));route.abort()
            else:route.continue_()
        # Keep the shipped views and shared controls. Replace only game discovery
        # and shell startup, so CI needs no private game installation.
        boot=(Path(__file__).resolve().parents[2]/'plugins/ff8/boot.js').read_text(encoding='utf-8')
        rows=[{'id':mod_id,'name':name,'enabled':False,'trust':'trusted','values':{},
               'schema':{'title':name.upper(),'help':help_text,'needsDriver':True,'fields':[]}}
              for mod_id,name,help_text in [('better-hp-colors','Better HP Colors',HELP),
                                             ('interaction-indicators','Interaction Indicators','')]]
        boot=boot[:boot.index('  const shell=LexeditorUI.mountShell(')]+'''
const shell={refresh(){}};
state.data.settings={tweaks:FIXTURE_ROWS};
state.settingsTab='gameplay';state.tab='settings';state.booting=false;state.activeSource='mine';
document.body.dataset.lexPlugin='ff8';renderSettings();LexeditorUI.finishPluginLoading();
'''.replace('FIXTURE_ROWS',json.dumps(rows))
        page.route('**/boot.js',lambda route:route.fulfill(content_type='application/javascript',body=boot))
        page.route("**/api/**",route_api);page.goto(f"http://127.0.0.1:{server.server_port}/")
        assert not errors,errors
        panel=page.locator('.lex-tweak-panel').filter(has_text='BETTER HP COLORS')
        panel.wait_for(state='attached');reveal(page,panel)
        assert panel.locator('.lex-badge').inner_text()=='OFF'
        assert panel.locator('input[type="checkbox"]').count()==0
        marker=panel.locator('.lex-info-help')
        marker.hover()
        page.wait_for_selector('.lex-help-popover')
        body=page.locator("body").inner_text()
        assert "BETTER HP COLORS" in body and "yellow at 50%" in body and "orange at 25%" in body and "KO" in body
        page.keyboard.press('Escape')
        # The Mods tab changes enabled metadata. Rendering that state must
        # leave the other mod off and never add a second toggle to Tweaks.
        page.evaluate("state.data.settings.tweaks[0].enabled=true;renderSettings()")
        reveal(page,panel)
        assert panel.locator('.lex-badge').count()==0
        indicator=page.locator('.lex-tweak-panel').filter(has_text='INTERACTION INDICATORS')
        reveal(page,indicator)
        assert indicator.locator('.lex-badge').inner_text()=='OFF'
        assert page.locator('.lex-tweak-panel input[type="checkbox"]').count()==0
        destination=Path(sys.argv[1]) if len(sys.argv)>1 else Path(tempfile.gettempdir())/'lexeditor-dev/ff8-hp-colors'
        destination.mkdir(parents=True,exist_ok=True)
        page.screenshot(path=str(destination/'hp-colors-schema.png'))
        assert not writes,writes;assert not errors,errors;browser.close()
    print("FF8 HP colors schema help and independent mod states passed; Mods owns toggles; no writes sent")
finally:
    server.shutdown();server.server_close();thread.join()
