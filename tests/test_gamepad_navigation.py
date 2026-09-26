"""Issue 566: the shared UI can be driven with a controller alone.

A scripted standard-mapping pad stands in for real hardware: the page reads
it through navigator.getGamepads exactly as it reads a real one, and the
check steps the shared reader frame by frame.
"""
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

PAGE = '''
<main id="main">
  <nav><button data-tab="a" class="active" onclick="tab('a')">A</button>
       <button data-tab="b" onclick="tab('b')">B</button>
       <button data-tab="c" onclick="tab('c')">C</button></nav>
  <div style="display:grid;grid-template-columns:repeat(3,120px);gap:20px;margin:40px">
    <button id="b1">1</button><button id="b2">2</button><button id="b3">3</button>
    <button id="b4">4</button><button id="b5">5</button><button id="b6">6</button>
  </div>
  <input id="count" type="number" min="0" max="3" step="1" value="1">
  <select id="kind"><option>Sword</option><option>Axe</option><option>Bow</option></select>
  <label><input id="flag" type="checkbox"> Flag</label>
  <input id="name" type="text" value="Cloud">
  <div class="lex-pager"><button aria-label="Previous page" onclick="pages.push(-1)">&lt;</button>
    <button aria-label="Next page" onclick="pages.push(1)">&gt;</button></div>
</main>
<script>window.tabs=[];window.pages=[];window.clicks=[];
function tab(id){tabs.push(id);document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('active',b.dataset.tab===id))}
document.addEventListener('click',e=>{if(e.target.id)clicks.push(e.target.id)});
window.pad={index:0,mapping:'standard',connected:true,axes:[0,0,0,0],
  buttons:Array.from({length:17},()=>({pressed:false,value:0}))};
navigator.getGamepads=()=>[window.pad];
window.press=async(index)=>{const t=performance.now();pad.buttons[index].pressed=true;
  LexeditorGamepad.step(t);pad.buttons[index].pressed=false;LexeditorGamepad.step(t+1)};
</script>'''

A, B, LB, RB, LT, RT, UP, DOWN, LEFT, RIGHT = 0, 1, 4, 5, 6, 7, 12, 13, 14, 15


@pytest.fixture
def page():
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1000, 'height': 700})
        page.route('http://fixture/**', lambda r: r.fulfill(body=PAGE, content_type='text/html'))
        page.goto('http://fixture/')
        page.add_style_tag(path=str(ROOT / 'ui/framework.css'))
        page.add_script_tag(path=str(ROOT / 'ui/framework.js'))
        yield page
        browser.close()


def press(page, button):
    page.evaluate('index => press(index)', button)


def focused(page):
    return page.evaluate('document.activeElement.id || document.activeElement.textContent')


def test_dpad_moves_focus_spatially_and_shows_it(page):
    page.focus('#b1')
    press(page, RIGHT)
    assert focused(page) == 'b2'
    press(page, DOWN)
    assert focused(page) == 'b5'
    press(page, LEFT)
    assert focused(page) == 'b4'
    press(page, UP)
    assert focused(page) == 'b1'
    assert page.evaluate("document.documentElement.classList.contains('lex-gamepad-active')")
    outline = page.evaluate("getComputedStyle(document.activeElement).outlineWidth")
    assert outline == '3px'
    page.mouse.move(5, 5)
    assert not page.evaluate("document.documentElement.classList.contains('lex-gamepad-active')")


def test_left_stick_moves_and_repeats_while_held(page):
    page.focus('#b1')
    page.evaluate('''() => { pad.axes[0] = 1; const g = LexeditorGamepad;
      g.step(1000); g.step(1100); g.step(1400); pad.axes[0] = 0; g.step(1500); }''')
    assert focused(page) == 'b3'


def test_a_activates_and_b_backs_out(page):
    page.focus('#b2')
    press(page, A)
    assert page.evaluate('clicks') == ['b2']
    page.evaluate('''() => {
      const U = LexeditorUI; window.dismissed = 0;
      const backdrop = U.el('div', {class: 'lex-dialog-backdrop'});
      const dialog = U.el('section', {class: 'lex-dialog', role: 'dialog', 'aria-modal': 'true'},
        U.el('button', {id: 'inside'}, 'OK'),
        U.el('button', {id: 'close', class: 'lex-close-button', onclick: () => { dismissed++; backdrop.remove(); }}, 'x'));
      backdrop.append(dialog); document.body.append(backdrop);
      document.querySelector('#inside').focus();
    }''')
    press(page, RIGHT)
    assert focused(page) == 'close', 'focus must stay inside the open dialog'
    press(page, LEFT)
    press(page, B)
    assert page.evaluate('dismissed') == 1


def test_left_right_adjust_values_in_place(page):
    page.focus('#count')
    press(page, RIGHT)
    press(page, RIGHT)
    assert page.input_value('#count') == '3'
    press(page, RIGHT)
    assert page.input_value('#count') == '3', 'the bound holds'
    assert focused(page) == 'count'
    page.focus('#kind')
    press(page, RIGHT)
    assert page.evaluate("document.querySelector('#kind').value") == 'Axe'
    press(page, LEFT)
    assert page.evaluate("document.querySelector('#kind').value") == 'Sword'
    page.focus('#flag')
    press(page, A)
    assert page.is_checked('#flag')


def test_bumpers_switch_tabs_and_triggers_turn_pages(page):
    page.focus('#b1')
    press(page, RB)
    press(page, RB)
    press(page, LB)
    assert page.evaluate('tabs') == ['b', 'c', 'b']
    press(page, RB)
    press(page, RB)
    assert page.evaluate('tabs')[-1] == 'a', 'tabs wrap around'
    press(page, RT)
    press(page, LT)
    assert page.evaluate('pages') == [1, -1]


def test_a_on_text_starts_typing_and_asks_for_the_keyboard(page):
    page.evaluate("window.keyboard = 0; window.pywebview = {api: {show_on_screen_keyboard: async () => { keyboard++; return {opened: true}; }}}")
    page.focus('#name')
    press(page, A)
    assert page.evaluate('keyboard') == 1
    press(page, DOWN)
    assert focused(page) == 'name', 'the D-pad does not leave a field being typed in'
    press(page, B)
    press(page, DOWN)
    assert focused(page) != 'name'


def test_editor_frame_owns_the_pad_while_open(page):
    page.focus('#b1')
    page.evaluate("document.body.append(Object.assign(document.createElement('iframe'), {id: 'lexeditor-editor'}))")
    press(page, RIGHT)
    assert focused(page) == 'b1'


def test_home_cards_are_reachable_and_open_with_a():
    import functools
    import json
    import threading
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=str(ROOT)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    rows = [{'id': f'game{n}', 'name': f'Game {n}', 'status': 'added', 'canOpen': True, 'ready': True,
             'coverArt': {'state': 'missing', 'uri': ''}} for n in range(3)]
    stub = ("window.opened=[];window.pywebview={api:new Proxy({"
            "lexeditor_settings:async()=>({viewPreferences:{},loadingTransitionMinimumSeconds:0}),"
            f"plugins:async()=>({json.dumps(rows)}),loading_quote:async()=>({{quote:''}}),"
            "open_plugin:async id=>{opened.push(id);throw new Error('stop')}"
            "},{get:(t,k)=>t[k]||(async()=>false)})};"
            "window.pad={index:0,mapping:'standard',connected:true,axes:[0,0],"
            "buttons:Array.from({length:17},()=>({pressed:false,value:0}))};"
            "navigator.getGamepads=()=>[window.pad];")
    try:
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1600, 'height': 900})
            page.add_init_script(stub)
            page.goto(f'http://127.0.0.1:{server.server_port}/ui/chooser.html')
            page.evaluate("dispatchEvent(new Event('pywebviewready'))")
            page.wait_for_selector('.game[data-plugin="game2"]', timeout=15000)
            page.focus('.game[data-plugin="game0"]')
            page.evaluate('''() => { const g = LexeditorGamepad; pad.buttons[15].pressed = true;
              g.step(1); pad.buttons[15].pressed = false; g.step(2); }''')
            assert page.evaluate('document.activeElement.dataset.plugin') == 'game1'
            page.evaluate('''() => { const g = LexeditorGamepad; pad.buttons[0].pressed = true;
              g.step(3); pad.buttons[0].pressed = false; g.step(4); }''')
            page.wait_for_function("opened.length > 0", timeout=5000)
            assert page.evaluate('opened') == ['game1']
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
