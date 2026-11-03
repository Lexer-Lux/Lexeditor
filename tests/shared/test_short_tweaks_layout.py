"""A game without ReShade for players shows no ReShade subtab.

FF7R2 kept a ReShade tab that only said ReShade was not set up. The shared
Tweaks page shows ReShade only where the host offers it (defaults saved, or
Developer Mode), so the page opens on Rebirth's own tools and fills the window.
"""
from pathlib import Path
import re
import tempfile

from playwright.sync_api import sync_playwright

from verify_no_dead_space import PROBE, STUB, session_for


def test_unavailable_reshade_has_no_subtab(tmp_path):
    plugin='ff7r2'
    with session_for(plugin, str(tmp_path/'project')) as session:
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(headless=True)
            page=browser.new_page(viewport={'width':1500,'height':950})
            errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.add_init_script(STUB)
            page.goto(session.url)
            page.wait_for_function("() => !document.documentElement.classList.contains('lex-loading-live')")
            page.locator("nav button[data-tab='tweaks']").click()
            page.wait_for_selector('#main .lex-tweaks-paged,#main .lex-tabbed-panel')
            page.wait_for_function("() => !document.querySelector('.lex-plugin-loading-screen')")
            page.wait_for_function("() => ![...document.querySelectorAll('#main .lex-panel-loading')].some(node=>node.getClientRects().length)")
            page.evaluate('() => new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
            output=Path(tempfile.gettempdir())/'lexeditor-dev/dead-space'/f'{plugin}-tweaks.png'
            output.parent.mkdir(parents=True,exist_ok=True)
            page.screenshot(path=str(output))
            measure=page.evaluate(PROBE)
            geometry=page.locator('#main,.lex-tweaks-paged,.lex-tweaks-scroll,.lex-tweaks-pages,.lex-pager').evaluate_all('''nodes=>nodes.map(node=>{
              const box=node.getBoundingClientRect(),style=getComputedStyle(node);
              return {class:node.className,height:box.height,top:box.top,bottom:box.bottom,
                display:style.display,position:style.position,text:node.textContent.slice(0,100)};
            })''')
            assert measure['bottom']-measure['lowest'] <= measure['height']*.2, geometry
            page.get_by_role('tab',name=re.compile('Engine Config',re.I)).click()
            page.locator('#main .lex-detail-panel-title').filter(has_text=re.compile('ENGINE CONFIG',re.I)).first.wait_for()
            assert page.locator('.lex-subtab-bar').first.locator('[role=tab]').count()==2
            assert page.get_by_role('tab',name=re.compile('ReShade',re.I)).count()==0
            page.get_by_role('tab',name=re.compile('Shader Injector',re.I)).click()
            page.wait_for_selector('#main .lex-tweaks-paged')
            assert not errors, errors
            browser.close()
