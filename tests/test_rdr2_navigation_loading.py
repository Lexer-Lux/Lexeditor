"""A delayed page read must not clear or replace the page selected meanwhile."""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def test_skinning_does_not_wait_for_an_unconfigured_reference():
    core=(ROOT/'plugins/rdr2/core.js').read_text(encoding='utf-8')
    helper=core[core.index('async function ensureRefMatrix('):core.index('\nfunction cashOf(')]
    loot=(ROOT/'plugins/rdr2/loot.js').read_text(encoding='utf-8')
    start=loot.index('async function renderMatrix()')
    renderer=loot[start:loot.index('  const tb =',start)]+'return state.matrix;}'
    with sync_playwright() as play:
        browser=play.chromium.launch(headless=True)
        try:
            page=browser.new_page()
            page.add_script_tag(content='''
              const state={ds:'mine',filters:{},store:{mine:{matrix:{animals:[]}},vanilla:{},kiddos:{}},config:{datasets:{vanilla:{matrix:false},kiddos:{matrix:false}}}};
              const refStore=ds=>state.store[ds],hasScope=()=>false;
              const dsInfo=()=>({matrix:true}),renderScope=()=>()=>true;
              const api=()=>{throw new Error('No request is needed')};
              const render=()=>{throw new Error('Recursive render')};
            '''+helper+renderer)
            assert page.evaluate('renderMatrix()')=={'animals':[]}
        finally:
            browser.close()


def test_delayed_settings_read_keeps_new_page():
    core = (ROOT / 'plugins/rdr2/core.js').read_text(encoding='utf-8')
    scope = core[core.index('let renderRevision='):core.index('function render() {')]
    tweaks = (ROOT / 'plugins/rdr2/tweaks.js').read_text(encoding='utf-8')
    renderer = tweaks[tweaks.index('async function renderSettings(){'):]
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_content('<div id="toolbar"></div><main id="main"></main>')
            page.add_script_tag(content='''
                const state={tab:'settings',ds:'mine',settings:null};
                const $=selector=>document.querySelector(selector);
                let finishRead;
                const api=()=>new Promise(resolve=>finishRead=resolve);
                const installTabContext=()=>{};
            ''' + scope + renderer)
            page.evaluate('''() => {
                window.pending=renderSettings();
                state.tab='items';renderRevision++;
                $('#toolbar').textContent='Items toolbar';
                $('#main').textContent='Selected item';
                finishRead({available:false});
                return window.pending;
            }''')
            assert page.locator('#main').inner_text() == 'Selected item'
            assert page.locator('#toolbar').inner_text() == 'Items toolbar'
        finally:
            browser.close()


def test_new_render_and_return_navigation_invalidate_old_scope():
    core = (ROOT / 'plugins/rdr2/core.js').read_text(encoding='utf-8')
    scope = core[core.index('let renderRevision='):core.index('function render() {')]
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.add_script_tag(content="const state={tab:'shops',ds:'mine'};" + scope)
            assert page.evaluate('''() => {
                const first=renderScope('shops');
                const second=renderScope('shops');
                if(first()||!second())return false;
                renderScope('shopChild');
                if(!second())return false;
                state.tab='items';renderRevision++;
                state.tab='shops';renderRevision++;
                return !second();
            }''')
        finally:
            browser.close()
