"""The shared UI is usable with a game controller and no mouse or keyboard.

Issue 566: Lexeditor has to work on a Steam Deck, whose controls arrive inside
the embedded page as one standard-mapped gamepad. The translation lives in the
shared UI so every plugin gets it, and these checks drive it through its test
seam - a pad source and a single tick - so the behaviour is proven without a
pad, a Deck or a physical frame.
"""
from pathlib import Path

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
