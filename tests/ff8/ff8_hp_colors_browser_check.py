"""Render and exercise default-off Better HP Colors without saving."""
import sys,threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from plugins.ff8.server import create_server
from playwright.sync_api import sync_playwright
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
        boot=boot[:boot.index('  const shell=LexeditorUI.mountShell(')]+'''
const shell={refresh(){}};
state.data.settings={betterHpColors:false,interactionIndicators:false,
  cameraSpeed:1,cameraSpeedMinimum:0.2,cameraSpeedMaximum:4,
  maxSpell:100,maxSpellMinimum:1,maxSpellMaximum:255};
state.settingsTab='gameplay';state.tab='settings';state.booting=false;state.activeSource='mine';
document.body.dataset.lexPlugin='ff8';renderSettings();LexeditorUI.finishPluginLoading();
'''
        page.route('**/boot.js',lambda route:route.fulfill(content_type='application/javascript',body=boot))
        page.route("**/api/**",route_api);page.goto(f"http://127.0.0.1:{server.server_port}/")
        assert not errors,errors
        field=page.get_by_label("Better HP Colors",exact=True)
        first=page.get_by_role("button",name="First page",exact=True)
        if first.count() and first.is_enabled():first.click()
        nxt=page.get_by_role("button",name="Next page",exact=True)
        for _ in range(40):
            if field.count() and field.is_visible():break
            if not nxt.count() or not nxt.is_enabled():break
            nxt.click();page.wait_for_timeout(80)
        field.wait_for();assert not field.is_checked()
        marker=page.locator('.lex-info-help[aria-label*="yellow at 50%"]')
        marker.hover()
        page.wait_for_selector('.lex-help-popover')
        body=page.locator("body").inner_text()
        assert "BETTER HP COLORS" in body and "yellow at 50%" in body and "orange at 25%" in body and "KO" in body
        field.check();assert field.is_checked();field.uncheck();assert not field.is_checked()
        indicator=page.get_by_label('Interaction Indicators',exact=True)
        first=page.get_by_role('button',name='First page',exact=True)
        if first.count() and first.is_enabled():first.click()
        for _ in range(40):
            if indicator.count() and indicator.is_visible():break
            if not nxt.count() or not nxt.is_enabled():break
            nxt.click();page.wait_for_timeout(80)
        indicator.wait_for();assert not indicator.is_checked()
        indicator.check();assert page.evaluate('state.data.settings.interactionIndicators')
        assert not page.evaluate('state.data.settings.betterHpColors')
        indicator.uncheck();assert not indicator.is_checked()
        assert not writes,writes;assert not errors,errors;browser.close()
    print("FF8 HP colours and interaction indicator toggles passed; help opens on hover; no writes sent")
finally:
    server.shutdown();server.server_close();thread.join()
