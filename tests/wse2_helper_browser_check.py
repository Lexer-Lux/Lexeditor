"""Render the real Home page; bridge calls use disposable fixture responses."""
from pathlib import Path
import json
import shutil
import sys
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'out/wse2-helper-browser'
SETTINGS={'lexerMode':True,'developerMode':False,'lexerAuthorized':True,'lexerLogin':'Lexer-Lux','loadingTransitionMinimumSeconds':0,'soundEnabled':False,'viewPreferences':{}}
HELPERS=[
 {'pluginId':'ff8','plugin':'Final Fantasy 8','helper':'FFNx','pinned':'1.24.3','installedVersion':'1.24.3','installedStatus':'installed','latest':'1.25.0','published':'2026-09-01T00:00:00Z','behind':True,'releaseNotes':'https://github.com/julianxhokaxhiu/FFNx/releases/tag/1.25.0'},
 {'pluginId':'ff9','plugin':'Final Fantasy 9','helper':'Memoria','pinned':'v2025.07.04','installedVersion':'v2025.07.04','error':'Fixture GitHub outage: this must not hide other helpers'},
 {'pluginId':'warband','plugin':'Mount & Blade: Warband','helper':'WSE2','pinned':'v1.1.5.1','packageVersion':'1.1.5.1-lex1','installedVersion':'v1.1.5.1','installedStatus':'verified','latest':'v1.1.5.1','published':'2026-08-28T20:12:29Z','behind':False,'releaseNotes':'https://github.com/Ruslan-700/WSE2-Releases/releases/tag/v1.1.5.1'},
]
PLUGIN={'id':'warband','name':'Mount & Blade: Warband','subtitle':'Warband','status':'broken','canOpen':False,'scanInProgress':False,'root':'C:/Fixture/Warband','problems':['WSE2 differs from the pinned package. Use Install/Repair WSE2.'],'statusText':'Broken','resident':False,'coverArt':{'state':'missing'},'helperName':'WSE2','helperInstalled':False,'helperInstallable':True}

def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    results=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=shutil.which('chromium') or None,headless=True,args=['--no-sandbox'])
        try:
            for width,height in [(900,620),(1440,900)]:
                page=browser.new_page(viewport={'width':width,'height':height});errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                html=(ROOT/'ui/chooser.html').read_text()
                html=html.replace('<link rel="stylesheet" href="framework.css">','<style>'+(ROOT/'ui/framework.css').read_text()+'</style>')
                for name in ('framework.js','editor-host.js'):
                    html=html.replace(f'<script src="{name}"></script>','<script>'+(ROOT/'ui'/name).read_text()+'</script>')
                page.set_content(html,wait_until='domcontentloaded')
                page.evaluate('''({settings,helpers,plugin})=>{
                    window.__testSettings=settings;window.__helperCalls=[];window.__installs=[];window.__notes=[];
                    window.pywebview={api:{
                        plugins:async()=>[plugin],window_state:async()=>({maximized:false}),
                        lexeditor_settings:async()=>settings,loading_quote:async()=>({quote:''}),
                        cover_art_data_uri:async()=>({uri:''}),
                        helper_versions:async refresh=>{window.__helperCalls.push(!!refresh);return {helpers,cached:!refresh}},
                        open_helper_release_notes:async id=>{window.__notes.push(id);return {opened:true}},
                        install_helper:async id=>{window.__installs.push(id);return {installed:true}},
                    }};
                    window.dispatchEvent(new Event('pywebviewready'));
                }''',{'settings':SETTINGS,'helpers':HELPERS,'plugin':PLUGIN})
                page.wait_for_function('!document.querySelector("#chooser-lexer").hidden')
                page.locator('#chooser-lexer').click();page.wait_for_function('document.querySelectorAll(".lexer-helper").length===3')
                page.wait_for_timeout(300)
                rows=page.locator('.lexer-helper')
                assert 'Installed: v1.1.5.1 (verified)' in rows.nth(2).inner_text()
                assert 'Package 1.1.5.1-lex1' in rows.nth(2).inner_text()
                assert '2026-08-28' in rows.nth(2).inner_text()
                assert 'Latest upstream: v1.1.5.1' in rows.nth(2).inner_text()
                assert 'Pinned: v2025.07.04' in rows.nth(1).inner_text()
                assert 'Installed: v2025.07.04' in rows.nth(1).inner_text()
                assert page.evaluate('window.__installs')==[]
                rows.nth(2).get_by_role('button',name='Release notes').click()
                assert page.evaluate('window.__notes')==['warband']
                page.locator('#lexer-panel-refresh').click()
                page.wait_for_function('window.__helperCalls.length===2')
                assert page.evaluate('window.__helperCalls')==[False,True]
                box=page.locator('#lexer-panel').bounding_box();assert box['x']>=0 and box['x']+box['width']<=width+1
                assert page.locator('#lexer-panel').evaluate('(el)=>el.scrollWidth<=el.clientWidth')
                page.screenshot(path=str(OUTPUT/f'helpers-{width}.png'))
                page.locator('#lexer-panel-close').click();page.wait_for_timeout(300)
                assert page.locator('[data-plugin="warband"] .state-label').inner_text()=='Broken'
                page.locator('[data-plugin="warband"]').click()
                page.get_by_role('button',name='INSTALL / REPAIR WSE2').wait_for()
                page.screenshot(path=str(OUTPUT/f'install-{width}.png'))
                assert page.evaluate('window.__installs')==[]
                page.get_by_role('button',name='INSTALL / REPAIR WSE2').click()
                page.wait_for_function('window.__installs.length===1')
                assert page.evaluate('window.__installs')==['warband']
                page.evaluate('window.dispatchEvent(new CustomEvent("lexeditor-settings-changed",{detail:{lexerMode:false}}))')
                assert page.locator('#chooser-lexer').is_hidden()
                assert errors==[],errors
                results.append({'width':width,'height':height,'passed':True,'bridge':'fixture responses, real HTML/CSS/JS'})
                page.close()
        finally:browser.close()
    (OUTPUT/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results))

if __name__=='__main__':main()
