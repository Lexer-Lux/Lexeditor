"""Render the FF8 Formulae tweaks subtab and prove its lowest card stays reachable.

Issue #31: the Formulae page is a subtab under Tweaks that unlocks only
while the Formulae Rework tweak is enabled. The page stacks
physical-damage, physical-accuracy and one card per requested rework formula,
which runs taller than the main region, and the FF8 plugin clips #main. The
page must therefore mount inside the shared tweaks scroll container. This
check renders the page with stubbed data (CI needs no private game install),
scrolls the container to its end, and requires the last formula card to sit
inside the window. It then disables the tweak and requires the subtab to
fall back to the Gameplay list that owns the toggle. It sends no writes.
"""
import json
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plugins.ff8 import formulae_rework
from plugins.ff8.server import create_server
from playwright.sync_api import sync_playwright

FORMULA_ROWS = json.dumps(formulae_rework.rows(), ensure_ascii=True)

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
        # The rework rows come from the real backend contract, so the stub
        # renders the same inventory the game session would list.
        boot = (Path(__file__).resolve().parents[2] / "plugins/ff8/boot.js").read_text(encoding="utf-8")
        boot = boot[:boot.index("  const shell=LexeditorUI.mountShell(")] + """
const shell={refresh(){}};
state.formula={weaponId:0,strength:100,vitality:50,luck:20,eva:10,targetLuck:5,flying:false,float:false};
state.data={weapons:{rows:[]},settings:{formulaeRework:true,formulaeReworkAvailable:false,
  formulaeReworkFormulas:FORMULA_ROWS_PLACEHOLDER,
  flyingEvaEnabled:false,flyingEvaBonus:0,minimum:0,maximum:100,
  cameraSpeed:1,cameraSpeedMinimum:0.2,cameraSpeedMaximum:4,
  maxSpell:100,maxSpellMinimum:1,maxSpellMaximum:255}};
state.tab="settings";state.settingsTab="formulae";state.booting=false;state.activeSource="mine";
document.body.dataset.lexPlugin="ff8";renderSettings();LexeditorUI.finishPluginLoading();
""".replace("FORMULA_ROWS_PLACEHOLDER", FORMULA_ROWS)
        page.route("**/boot.js", lambda route: route.fulfill(
            content_type="application/javascript", body=boot))
        page.route("**/api/**", lambda route: route.abort())
        page.goto(f"http://127.0.0.1:{server.server_port}/")
        page.wait_for_selector("[data-formula-id]")
        assert not errors, errors
        unlocked = page.evaluate("""() => ({
          cards: [...document.querySelectorAll('.lex-detail-section-title')].map(node=>node.textContent.trim()),
          rework: [...document.querySelectorAll('[data-formula-id]')].map(node=>node.getAttribute('data-formula-id')),
          master: document.querySelector('.formulae-view')?.textContent ?? document.querySelector('#main').textContent,
          subtabs: [...document.querySelectorAll('.lex-subtab-button')].map(button=>({
            label: button.querySelector('.lex-tab-label-text').textContent.trim(), disabled: button.disabled,
            active: button.classList.contains('active')})),
        })""")
        assert unlocked["rework"] == [row["id"] for row in formulae_rework.rows()], unlocked["rework"]
        assert any("PHYSICAL DAMAGE" in card for card in unlocked["cards"]), unlocked["cards"]
        assert any("PHYSICAL ACCURACY" in card for card in unlocked["cards"]), unlocked["cards"]
        assert any("MELEE DAMAGE" in card and "INCOMPLETE" in card for card in unlocked["cards"]), unlocked["cards"]
        assert any("SPELL HEALING" in card and "IMPLEMENTED" in card for card in unlocked["cards"]), unlocked["cards"]
        assert "2/6 requested runtime formulae are implemented" in unlocked["master"], unlocked["master"]
        formulae_tab = next(tab for tab in unlocked["subtabs"] if tab["label"] == "Formulae")
        assert formulae_tab == {"label": "Formulae", "disabled": False, "active": True}, unlocked["subtabs"]
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
        assert metrics["cards"] == len(formulae_rework.rows()), metrics
        assert metrics["scrollerFound"], metrics
        assert metrics["overflowY"] == "auto", metrics
        assert metrics["scrollable"] > 0, metrics
        assert metrics["lastBottom"] <= metrics["viewport"], metrics
        # Locking the owning tweak must fall back to the Gameplay list that
        # owns the toggle instead of stranding the viewer on a locked subtab.
        locked = page.evaluate("""() => {
          state.data.settings.formulaeRework = false;
          renderSettings();
          return {
            settingsTab: state.settingsTab,
            formulaCards: document.querySelectorAll('[data-formula-id]').length,
            gameplay: !!document.querySelector('.lex-settings-columns') && document.querySelector('#main').textContent.includes('FLAT +STAT ABILITIES'),
            tweak: (() => { const input = document.querySelector('[aria-label="Formulae Rework"]');
              return input ? {disabled: input.disabled} : null; })(),
            subtabs: [...document.querySelectorAll('.lex-subtab-button')].map(button=>({
              label: button.querySelector('.lex-tab-label-text').textContent.trim(), disabled: button.disabled,
              active: button.classList.contains('active')})),
          };
        }""")
        assert not errors, errors
        assert locked["settingsTab"] == "gameplay", locked
        assert locked["formulaCards"] == 0, locked
        assert locked["gameplay"], locked
        assert locked["tweak"] == {"disabled": True}, locked
        formulae_tab = next(tab for tab in locked["subtabs"] if tab["label"] == "Formulae")
        assert formulae_tab["disabled"] is True, locked["subtabs"]
        browser.close()
    print("PASS: Formulae tweaks subtab scrolls when unlocked and falls back to Gameplay when locked")
finally:
    server.shutdown()
    server.server_close()
    thread.join()
