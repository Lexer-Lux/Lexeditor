"""Render the FF8 Formulae page and prove its lowest card stays reachable.

Issue #31 reported that the Formulae page does not scroll. The page stacks
physical-damage, physical-accuracy and one card per requested rework formula,
which runs taller than the main region, and the FF8 plugin clips #main. The
page must therefore mount inside the shared tweaks scroll container. This
check renders the page with stubbed data (CI needs no private game install),
scrolls the container to its end, and requires the last formula card to sit
inside the window. It sends no writes.
"""
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from games.ff8.server import create_server
from playwright.sync_api import sync_playwright

server = create_server(0)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        # Keep the shipped views and shared controls. Replace only game
        # discovery and shell startup, so CI needs no private installation.
        boot = (Path(__file__).resolve().parents[1] / "games/ff8/boot.js").read_text(encoding="utf-8")
        boot = boot[:boot.index("  const shell=LexeditorUI.mountShell(")] + """
const shell={refresh(){}};
state.formula={weaponId:0,strength:100,vitality:50,luck:20,eva:10,targetLuck:5,flying:false,float:false};
state.data={weapons:{rows:[]},settings:{formulaeRework:false,formulaeReworkAvailable:false,
  formulaeReworkFormulas:[{id:"mug",name:"Mug",status:"incomplete",replacement:"X",vanilla:"Y",blocker:"Z"}],
  flyingEvaEnabled:false,flyingEvaBonus:0}};
state.tab="formulae";state.booting=false;state.activeSource="mine";
document.body.dataset.lexPlugin="ff8";renderFormulae();LexeditorUI.finishPluginLoading();
"""
        page.route("**/boot.js", lambda route: route.fulfill(
            content_type="application/javascript", body=boot))
        page.route("**/api/**", lambda route: route.abort())
        page.goto(f"http://127.0.0.1:{server.server_port}/")
        page.wait_for_selector("[data-formula-id]")
        assert not errors, errors
        metrics = page.evaluate("""() => {
          const main = document.querySelector("#main");
          const scroller = main ? main.querySelector(".lex-tweaks-scroll") : null;
          const cards = [...document.querySelectorAll("[data-formula-id]")];
          const last = cards[cards.length - 1];
          if (scroller) scroller.scrollTop = scroller.scrollHeight;
          const rect = last ? last.getBoundingClientRect() : null;
          const style = scroller ? getComputedStyle(scroller) : null;
          return {
            cards: cards.length,
            scrollerFound: !!scroller,
            overflowY: style && style.overflowY,
            scrollable: scroller ? scroller.scrollHeight - scroller.clientHeight : 0,
            lastBottom: rect ? rect.bottom : 0,
            viewport: window.innerHeight,
          };
        }""")
        assert metrics["cards"] == 1, metrics
        assert metrics["scrollerFound"], metrics
        assert metrics["overflowY"] == "auto", metrics
        assert metrics["scrollable"] > 0, metrics
        assert metrics["lastBottom"] <= metrics["viewport"], metrics
        browser.close()
    print("PASS: Formulae page scrolls; every formula card is reachable")
finally:
    server.shutdown()
    server.server_close()
    thread.join()
