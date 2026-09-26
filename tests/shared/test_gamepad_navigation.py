"""The shared UI is usable with a game controller and no mouse or keyboard.

Issue 566: Lexeditor has to work on a Steam Deck, whose controls arrive inside
the embedded page as one standard-mapped gamepad. The translation lives in the
shared UI so every plugin gets it, and these checks drive it through its test
seam - a pad source and a single tick - so the behaviour is proven without a
pad, a Deck or a physical frame.
"""
import functools
import json
from pathlib import Path
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]

PAGE = """
<div class="lex-shell">
  <header class="lex-shell-header">
    <nav>
      <button type="button" data-tab="one" class="active">One</button>
      <button type="button" data-tab="two">Two</button>
    </nav>
  </header>
  <main id="main">
    <div class="lex-panel">
      <button type="button" id="first-action">First action</button>
      <button type="button" id="second-action">Second action</button>
      <input id="amount" type="number" value="10" min="0" max="20" step="5" aria-label="Amount">
      <input id="name" type="text" value="Griever" aria-label="Name">
      <select id="mode" aria-label="Mode">
        <option>Alpha</option><option>Beta</option><option>Gamma</option>
      </select>
      <input id="level" type="range" min="0" max="100" value="50" step="10" aria-label="Level">
      <div class="lex-pager">
        <button type="button" title="Previous page">&lt;</button>
        <button type="button" title="Next page">&gt;</button>
      </div>
    </div>
  </main>
</div>
"""


def _page(browser):
    page = browser.new_page(viewport={"width": 1100, "height": 800})
    page.route("http://fixture/**", lambda route: route.fulfill(
        body=PAGE, content_type="text/html"))
    # The on-screen keyboard is what the Deck shows for text entry and is
    # absent in a headless browser, so the request for it is recorded instead.
    page.add_init_script("""
      window.__events = [];
      window.__osk = 0;
      navigator.virtualKeyboard = {show(){ window.__osk += 1; }};
    """)
    page.goto("http://fixture/")
    page.add_style_tag(path=str(ROOT / "ui/framework.css"))
    # The fixture's own layout, so a direction has one answer: the tabs across
    # the top and one column of controls under them.
    page.add_style_tag(content="""
      body{margin:0;font:14px sans-serif}
      .lex-shell-header nav{display:flex;gap:4px;padding:4px}
      #main{padding:8px}
      .lex-panel{display:flex;flex-direction:column;gap:12px;align-items:flex-start;width:260px}
      .lex-panel button,.lex-panel input,.lex-panel select{width:240px}
      .lex-pager{display:flex;gap:4px}
    """)
    page.add_script_tag(path=str(ROOT / "ui/framework.js"))
    page.evaluate("""()=>{
      window.__lexeditorNavigateHistory = direction => window.__events.push('back:'+direction);
      window.__pad = {index:0, id:'fixture pad', connected:true, mapping:'standard',
        axes:[0,0,0,0],
        buttons:Array.from({length:17},()=>({pressed:false,value:0}))};
      window.__press = (index,down=true)=>{window.__pad.buttons[index].pressed=down;
        window.__pad.buttons[index].value=down?1:0;};
      window.__axis = (x,y)=>{window.__pad.axes=[x,y,0,0];};
      const pad=LexeditorUI.gamepadNavigation;
      pad.setPadSource(()=>[window.__pad]);
      // The live loop is what the Deck runs; a check drives tick() instead so
      // the timing of every step is the check's, not the frame clock's.
      pad.uninstall();
      for(const id of ['first-action','second-action']){
        document.getElementById(id).addEventListener('click',
          ()=>window.__events.push(id));
      }
      document.querySelector('.lex-pager button[title="Next page"]').addEventListener(
        'click',()=>window.__events.push('next-page'));
      document.querySelector('nav').addEventListener('click',event=>{
        const button=event.target.closest('button[data-tab]');
        if(!button)return;
        for(const tab of document.querySelectorAll('nav button[data-tab]')){
          tab.classList.toggle('active',tab===button);
        }
        window.__events.push('tab:'+button.dataset.tab);
      });
      for(const id of ['amount','level','mode','name']){
        for(const type of ['input','change']){
          document.getElementById(id).addEventListener(type,
            ()=>window.__events.push(id+':'+type+':'+document.getElementById(id).value));
        }
      }
    }""")
    return page


def _tick(page, now=0):
    return page.evaluate("now=>LexeditorUI.gamepadNavigation.tick(now)", now)


def _focused(page):
    return page.evaluate("()=>document.activeElement?.id||document.activeElement?.dataset?.tab"
                         "||document.activeElement?.textContent?.trim()||''")


def test_the_pad_walks_the_interface_and_activates_what_it_reaches():
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = _page(browser)
            assert page.evaluate("()=>!!LexeditorUI.gamepadNavigation")
            # No pad attached changes nothing at all.
            page.evaluate("()=>LexeditorUI.gamepadNavigation.setPadSource(()=>[])")
            assert _tick(page) is False

            page.evaluate("()=>LexeditorUI.gamepadNavigation.setPadSource(()=>[window.__pad])")
            assert _tick(page) is True
            # A direction with nothing focused yet lands on the first control
            # that can be reached, and it is visibly marked.
            page.evaluate("()=>window.__press(13)")
            _tick(page)
            assert _focused(page) == "one", _focused(page)
            assert page.evaluate(
                "()=>document.activeElement.classList.contains('lex-pad-focus')")
            page.evaluate("()=>window.__press(13,false)")
            _tick(page, 900)
            page.evaluate("()=>window.__press(13)")
            _tick(page, 1000)
            assert _focused(page) == "first-action", _focused(page)
            page.evaluate("()=>window.__press(13,false)")
            _tick(page, 1100)
            page.evaluate("()=>window.__press(13)")
            _tick(page, 1200)
            assert _focused(page) == "second-action", _focused(page)
            page.evaluate("()=>window.__press(13,false)")
            _tick(page, 1300)

            # B is back: the one Escape reaches the document, where the page's
            # own handlers are, and the shell's own history takes the step a
            # console player expects when there was nothing to close.
            page.evaluate("""()=>{
              window.__events.length=0;
              document.addEventListener('keydown',event=>{
                if(event.key==='Escape')window.__events.push('escape');
              },true);
              window.__press(1);
            }""")
            _tick(page, 1400)
            assert page.evaluate("()=>window.__events") == ["escape", "back:-1"], \
                page.evaluate("()=>window.__events")
            page.evaluate("()=>window.__press(1,false)")
            _tick(page, 1500)

            # A activates the control the pad is on.
            page.evaluate("""()=>{
              window.__events.length=0;
              document.getElementById('first-action').focus();
              window.__press(0);
            }""")
            _tick(page, 1600)
            assert page.evaluate("()=>window.__events") == ["first-action"]
            page.evaluate("()=>window.__press(0,false)")
            _tick(page, 1700)
        finally:
            browser.close()


def test_a_held_direction_repeats_and_text_entry_asks_for_the_keyboard():
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = _page(browser)
            # Holding a direction walks on past the first control: the first
            # step is immediate, the rest come from the repeat once the pad
            # has been held for its own first-step delay.
            page.evaluate("()=>LexeditorUI.gamepadNavigation.setPadFocus("
                          "document.getElementById('first-action'))")
            page.evaluate("()=>window.__press(13)")
            _tick(page, 0)
            assert _focused(page) == "second-action", _focused(page)
            _tick(page, 100)
            assert _focused(page) == "second-action", _focused(page)
            _tick(page, 500)
            assert _focused(page) != "second-action", _focused(page)
            page.evaluate("()=>window.__press(13,false)")
            _tick(page, 600)

            # Text entry focuses a real field and asks for the on-screen
            # keyboard the Deck shows for it.
            page.evaluate("""()=>{
              window.__osk=0;
              document.getElementById('name').focus();
              window.__press(0);
            }""")
            _tick(page, 700)
            assert page.evaluate("()=>window.__osk") == 1
            assert page.evaluate(
                "()=>document.getElementById('name').getAttribute('enterkeyhint')") == "done"
            page.evaluate("()=>window.__press(0,false)")
            _tick(page, 800)
        finally:
            browser.close()


def test_b_closes_a_shared_dialog_and_a_broken_pad_is_survivable():
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = _page(browser)
            page.evaluate("""()=>LexeditorUI.showAlert({title:'Could not launch the game',
              message:'The game is not installed.'});""")
            page.wait_for_selector(".lex-dialog")
            page.evaluate("""()=>{
              window.__events.length=0;
              window.__press(1);
            }""")
            _tick(page, 0)
            page.wait_for_timeout(200)
            assert page.locator(".lex-dialog").count() == 0
            # A dialog the pad closed does not also walk the page back.
            assert page.evaluate("()=>window.__events") == [], \
                page.evaluate("()=>window.__events")
            page.evaluate("()=>window.__press(1,false)")
            _tick(page, 100)

            # A page whose pad access throws must simply stop seeing input.
            page.evaluate("()=>LexeditorUI.gamepadNavigation.setPadSource("
                          "()=>{throw new Error('gone')})")
            assert _tick(page) is False
            page.evaluate("()=>LexeditorUI.gamepadNavigation.setPadSource(()=>[null])")
            assert _tick(page) is False
        finally:
            browser.close()


def test_the_web_gamepad_api_starts_the_loop_without_a_connection_event():
    """A Deck wakes the page with the pad already attached.

    Nothing fires `gamepadconnected` in that case, so the loop has to notice a
    pad that was there all along. This drives the real API path rather than the
    test seam.
    """
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = _page(browser)
            page.evaluate("""()=>{
              window.__pad.buttons[13].pressed = true;
              window.__pad.buttons[13].value = 1;
              LexeditorUI.gamepadNavigation.uninstall();
              LexeditorUI.gamepadNavigation.install();
            }""")
            page.wait_for_function(
                "()=>document.activeElement?.classList.contains('lex-pad-focus')",
                timeout=5000)
            assert page.evaluate(
                "()=>document.activeElement.classList.contains('lex-pad-focus')")
        finally:
            browser.close()


def test_the_pad_changes_values_pages_and_tabs():
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = _page(browser)
            pad = "LexeditorUI.gamepadNavigation"
            # A number field is bounded, so left and right move it, clamped,
            # and send the same events a typed edit does.
            page.evaluate("()=>LexeditorUI.gamepadNavigation.setPadFocus("
                          "document.getElementById('amount'))")
            page.evaluate("()=>window.__press(15)")
            _tick(page, 0)
            assert page.evaluate("()=>document.getElementById('amount').value") == "15"
            page.evaluate("()=>window.__press(15,false)")
            _tick(page, 100)
            for step in range(4):
                _tick(page, 200 + step * 100)
                page.evaluate("()=>window.__press(15)")
                _tick(page, 250 + step * 100)
                page.evaluate("()=>window.__press(15,false)")
                _tick(page, 300 + step * 100)
            assert page.evaluate("()=>document.getElementById('amount').value") == "20"
            assert page.evaluate(
                "()=>window.__events.filter(e=>e.startsWith('amount:change')).length") >= 2

            page.evaluate("()=>LexeditorUI.gamepadNavigation.setPadFocus("
                          "document.getElementById('level'))")
            page.evaluate("()=>window.__press(14)")
            _tick(page, 2000)
            assert page.evaluate("()=>document.getElementById('level').value") == "40"
            page.evaluate("()=>window.__press(14,false)")
            _tick(page, 2100)

            # A known set of choices is a select, and the pad moves through it.
            page.evaluate("()=>LexeditorUI.gamepadNavigation.setPadFocus("
                          "document.getElementById('mode'))")
            page.evaluate("()=>window.__press(15)")
            _tick(page, 2200)
            assert page.evaluate("()=>document.getElementById('mode').value") == "Beta"
            page.evaluate("()=>window.__press(15,false)")
            _tick(page, 2300)

            # The bumpers are the tabs, and the triggers page the list.
            page.evaluate("()=>window.__events.length=0")
            page.evaluate("()=>window.__press(5)")
            _tick(page, 2400)
            page.evaluate("()=>window.__press(5,false)")
            _tick(page, 2500)
            assert page.evaluate("()=>window.__events") == ["tab:two"], \
                page.evaluate("()=>window.__events")
            assert page.evaluate(
                "()=>document.querySelector('nav button.active').dataset.tab") == "two"

            page.evaluate("()=>window.__events.length=0")
            page.evaluate("()=>window.__press(7)")
            _tick(page, 2600)
            assert page.evaluate("()=>window.__events") == ["next-page"], \
                page.evaluate("()=>window.__events")
            page.evaluate("()=>window.__press(7,false)")
            _tick(page, 2700)

            # The left stick walks the same way the d-pad does.
            page.evaluate("""()=>{
              window.__events.length=0;
              document.getElementById('first-action').focus();
              window.__axis(0,-1);
            }""")
            _tick(page, 2800)
            assert _focused(page) != "first-action", _focused(page)
        finally:
            browser.close()


def _shell_page(browser):
    """The real shared shell, mounted the way a plugin mounts it."""
    page = browser.new_page(viewport={"width": 1280, "height": 820})
    page.route("http://fixture/**", lambda route: route.fulfill(
        body='<div id="shell"></div><main id="main"></main>', content_type="text/html"))
    page.add_init_script("window.__osk = 0;"
                         "navigator.virtualKeyboard = {show(){ window.__osk += 1; }};")
    page.goto("http://fixture/")
    page.add_style_tag(path=str(ROOT / "ui/framework.css"))
    page.add_script_tag(path=str(ROOT / "ui/framework.js"))
    page.evaluate("""()=>{
      window.__pad = {index:0, id:'fixture pad', connected:true, mapping:'standard',
        axes:[0,0,0,0],
        buttons:Array.from({length:17},()=>({pressed:false,value:0}))};
      window.__press = (index,down=true)=>{window.__pad.buttons[index].pressed=down;
        window.__pad.buttons[index].value=down?1:0;};
      const pad=LexeditorUI.gamepadNavigation;
      pad.setPadSource(()=>[window.__pad]);
      pad.uninstall();
      let shell;
      window.__active='one';
      shell=LexeditorUI.mountShell({
        host:'#shell', plugin:{id:'fixture',name:'Fixture'},
        tabs:[{id:'one',label:'One'},{id:'two',label:'Two'}],
        activeTab:()=>window.__active,
        navigate:id=>{window.__navigated=id;window.__active=id;shell.refresh();},
        dirtyCount:()=>0, save:async()=>{},
      });
      const field=document.createElement('input');
      field.type='text'; field.value='Original'; field.id='shell-field';
      field.setAttribute('aria-label','Field');
      document.querySelector('#main').append(field);
    }""")
    return page


def test_the_real_shell_takes_the_bumpers_and_the_pad_focus_ring():
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = _shell_page(browser)
            # The bumpers are the shell's own tabs.
            page.evaluate("()=>window.__press(5)")
            _tick(page, 0)
            assert page.evaluate("()=>window.__navigated") == "two"
            assert page.evaluate(
                "()=>document.querySelector('nav button.active')?.dataset.tab") == "two"
            page.evaluate("()=>window.__press(5,false)")
            _tick(page, 100)

            # A direction puts the pad's ring on a real shell control.
            page.evaluate("()=>window.__press(13)")
            _tick(page, 200)
            marked = page.evaluate("""()=>{
              const node=document.querySelector('.lex-pad-focus');
              return node?{tab:node.dataset.tab||'', tag:node.tagName,
                inShell:!!node.closest('.lex-shell')
                  ||!!node.closest('nav')||!!node.closest('#main')}:null;
            }""")
            assert marked and (marked["tab"] or marked["inShell"]), marked
            page.evaluate("()=>window.__press(13,false)")
            _tick(page, 300)

            # A on a text field is the Deck's text entry, on the real shell.
            page.evaluate("""()=>{
              document.getElementById('shell-field').focus();
              window.__press(0);
            }""")
            _tick(page, 400)
            assert page.evaluate("()=>window.__osk") == 1
            page.evaluate("()=>window.__press(0,false)")
            _tick(page, 500)
            assert page.locator(".lex-pad-focus").count() == 1
        finally:
            browser.close()


class _Handler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def test_the_home_screen_walks_its_cards_and_opens_settings():
    """Home is the first screen a Deck player sees, and it is not a plugin."""
    base_settings = json.loads((ROOT / "ui/default_settings.json").read_text(encoding="utf-8"))
    settings = dict(base_settings, developerMode=False, developerAuthorized=False,
                    viewPreferences={}, defaultValues=dict(base_settings),
                    loadingTransitionMinimumSeconds=0,
                    updateCheckChoices=[{"value": "monthly", "label": "Monthly"}])
    plugins = [
        {"id": "with-cover", "name": "With Cover", "status": "added", "canOpen": True,
         "coverArt": {"state": "missing", "uri": "", "error": "none"}},
        {"id": "no-cover", "name": "No Cover Game", "status": "added", "canOpen": True,
         "coverArt": {"state": "missing", "uri": "", "error": "none"}},
    ]
    server = ThreadingHTTPServer(("127.0.0.1", 0),
                                 functools.partial(_Handler, directory=str(ROOT)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        stub = (
            f"window.pywebview={{api:new Proxy({{lexeditor_settings:async()=>({json.dumps(settings)}),"
            f"plugins:async()=>({json.dumps(plugins)}),"
            # Opening a game is the one action Home exists for; recording it
            # and stopping there keeps the check on this page.
            "open_plugin:async(id)=>{window.__opened=id;throw new Error('held for the check');},"
            "loading_quote:async()=>({quote:''}),app_update_status:async()=>({available:false}),"
            "window_state:async()=>({maximized:false}),game_process_status:async()=>({running:false}),"
            "theme_sounds:async()=>({rows:[]}),helper_versions:async()=>({helpers:[]}),"
            "project_info:async()=>({canCreate:false,projects:[]})},"
            "{get:(t,k)=>t[k]||(async()=>false)})};")
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1600, "height": 900})
                page.add_init_script(stub)
                page.goto(base + "/ui/chooser.html")
                page.evaluate("dispatchEvent(new Event('pywebviewready'))")
                page.wait_for_selector(".game", timeout=15000)
                page.evaluate("""()=>{
                  window.__pad = {index:0, id:'fixture pad', connected:true,
                    mapping:'standard', axes:[0,0,0,0],
                    buttons:Array.from({length:17},()=>({pressed:false,value:0}))};
                  window.__press = (index,down=true)=>{
                    window.__pad.buttons[index].pressed=down;
                    window.__pad.buttons[index].value=down?1:0;};
                  const pad=LexeditorUI.gamepadNavigation;
                  pad.setPadSource(()=>[window.__pad]);
                  pad.uninstall();
                }""")
                # A direction lands on something the player can act on, and it
                # is marked where it is.
                page.evaluate("()=>window.__press(13)")
                _tick(page, 0)
                marked = page.evaluate("""()=>{
                  const node=document.querySelector('.lex-pad-focus');
                  return node?{tag:node.tagName,cls:String(node.className),
                    onCard:!!node.closest('.game')}:null;
                }""")
                assert marked, "the pad found nothing on Home"
                page.evaluate("()=>window.__press(13,false)")
                _tick(page, 100)
                # A on a game card opens that game, which is what Home is for.
                page.evaluate("""()=>{
                  LexeditorUI.gamepadNavigation.setPadFocus(
                    document.querySelector('.game[data-plugin="with-cover"]'));
                  window.__press(0);
                }""")
                _tick(page, 150)
                page.wait_for_function("()=>window.__opened==='with-cover'", timeout=5000)
                page.evaluate("()=>window.__press(0,false)")
                _tick(page, 180)
                # The host refused the open, so Home answers with its own
                # dialog; B is back out of it before anything else is touched.
                page.evaluate("()=>window.__press(1)")
                _tick(page, 190)
                assert page.evaluate(
                    "()=>document.querySelector('#modal').hidden") is True, \
                    "B left Home's own dialog open"
                page.evaluate("()=>window.__press(1,false)")
                _tick(page, 200)
                # A on the settings button opens the shared settings panel.
                page.wait_for_selector("#chooser-settings", timeout=10000)
                page.evaluate("""()=>{
                  LexeditorUI.gamepadNavigation.setPadFocus(
                    document.getElementById('chooser-settings'));
                  window.__press(0);
                }""")
                _tick(page, 300)
                page.wait_for_selector(".lex-global-settings", state="visible", timeout=10000)
                page.evaluate("()=>window.__press(0,false)")
                _tick(page, 300)
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
