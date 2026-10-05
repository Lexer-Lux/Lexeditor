"""Render the FF8 Formulae tweaks subtab and prove its lowest card stays reachable.

Issue #31: the Formulae page is a subtab under Tweaks that remains available
while the Formulae Rework tweak is disabled. The page stacks
physical-damage, physical-accuracy and one card per requested rework formula,
which runs taller than the main region, and the FF8 plugin clips #main. The
page must therefore mount inside the shared tweaks scroll container. This
check renders the page with stubbed data (CI needs no private game install),
scrolls the container to its end, and requires the last formula card to sit
inside the window. It then turns the tweak off and requires the subtab to
stay open on the same cards. It sends no writes.
"""
import json
import os
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core import script_mods
from plugins.ff8.server import create_server
from playwright.sync_api import sync_playwright

# Layout fixtures are intentionally independent of any installed tweak's
# formulas or native payload. Their inventory belongs to a temporary mod.
rows = [dict(id=key, name=name, status="implemented", replacement="fixture replacement",
             vanilla="fixture vanilla", enemies="fixture enemy rule")
        for key, name in (("melee_damage", "Melee damage"),
                          ("spell_healing", "Spell healing"),
                          *[(f"formula_{i}", f"Formula {i}") for i in range(10)])]
fixture = tempfile.TemporaryDirectory(prefix="lexeditor-formula-scroll-")
mod = Path(fixture.name) / "project" / ".lexeditor-mods" / "Formulae Rework"
(mod / "script").mkdir(parents=True)
(mod / "mod.json").write_text(json.dumps({"id": "formulae-rework", "name": "Formulae Rework",
    "enabled": True, "script": {"version": 1}}), encoding="utf-8")
(mod / "settings.schema.json").write_text(json.dumps({"title": "FORMULAE REWORK"}), encoding="utf-8")
(mod / "script" / "__init__.py").write_text("", encoding="utf-8")
(mod / "script" / "tweak.py").write_text(
    "def build(settings, context):\n    return {}\n\ndef describe(settings, context):\n    return "
    + repr({"formulas": rows, "available": True, "blocker": ""}) + "\n", encoding="utf-8")
previous_trust = os.environ.get(script_mods.TRUST_ENV)
os.environ[script_mods.TRUST_ENV] = str(Path(fixture.name) / "trust.json")
try:
    script_mods.set_trusted(mod, True)
    described = script_mods.describe(mod, None)
finally:
    if previous_trust is None:
        os.environ.pop(script_mods.TRUST_ENV, None)
    else:
        os.environ[script_mods.TRUST_ENV] = previous_trust
FORMULA_DESCRIPTION = json.dumps(described, ensure_ascii=True)

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
        # The rows cross the trusted-mod describe() contract above; their
        # arithmetic is fixture text, since this checks layout rather than game code.
        boot = (Path(__file__).resolve().parents[2] / "plugins/ff8/boot.js").read_text(encoding="utf-8")
        boot = boot[:boot.index("  const shell=LexeditorUI.mountShell(")] + """
const shell={refresh(){}};
state.formula={weaponId:0,strength:100,vitality:50,luck:20,eva:10,targetLuck:5,flying:false,float:false};
state.data={weapons:{rows:[]},settings:{tweaks:[{id:"formulae-rework",enabled:true,
  schema:{},describe:FORMULA_DESCRIPTION_PLACEHOLDER}],
  minimum:0,maximum:100,
  cameraSpeed:1,cameraSpeedMinimum:0.2,cameraSpeedMaximum:4,
  maxSpell:100,maxSpellMinimum:1,maxSpellMaximum:255}};
state.tab="settings";state.settingsTab="formulae";state.booting=false;state.activeSource="mine";
document.body.dataset.lexPlugin="ff8";renderSettings();LexeditorUI.finishPluginLoading();
""".replace("FORMULA_DESCRIPTION_PLACEHOLDER", FORMULA_DESCRIPTION)
        page.route("**/boot.js", lambda route: route.fulfill(
            content_type="application/javascript", body=boot))
        page.route("**/api/**", lambda route: route.abort())
        page.goto(f"http://127.0.0.1:{server.server_port}/")
        page.wait_for_selector("[data-formula-id]")
        page.wait_for_function("!document.documentElement.classList.contains('lex-loading-live')")
        page.locator('.lex-plugin-loading-screen').wait_for(state='detached')
        assert not errors, errors
        unlocked = page.evaluate("""() => ({
          cards: [...document.querySelectorAll('.lex-detail-section-title')].map(node=>node.textContent.trim()),
          rework: [...document.querySelectorAll('[data-formula-id]')].map(node=>node.getAttribute('data-formula-id')),
          master: document.querySelector('.formulae-view')?.textContent ?? document.querySelector('#main').textContent,
          subtabs: [...document.querySelectorAll('.lex-subtab-button')].map(button=>({
            label: button.querySelector('.lex-tab-label-text').textContent.trim(), disabled: button.disabled,
            active: button.classList.contains('active')})),
        })""")
        assert unlocked["rework"] == [row["id"] for row in rows], unlocked["rework"]
        assert any("PHYSICAL DAMAGE" in card for card in unlocked["cards"]), unlocked["cards"]
        assert any("PHYSICAL ACCURACY" in card for card in unlocked["cards"]), unlocked["cards"]
        assert any("MELEE DAMAGE" in card and "IMPLEMENTED" in card for card in unlocked["cards"]), unlocked["cards"]
        assert "ENEMIES" in unlocked["cards"], unlocked["cards"]
        assert not any("INCOMPLETE" in card for card in unlocked["cards"]), unlocked["cards"]
        assert any("SPELL HEALING" in card and "IMPLEMENTED" in card for card in unlocked["cards"]), unlocked["cards"]
        implemented = sum(row["status"] == "implemented" for row in rows)
        # The count is in the Formulae Rework section's help bubble, not on the page.
        count = f"{implemented} of the {len(rows)} requested formulae have a game patch."
        helps = page.evaluate("()=>[...document.querySelectorAll('.lex-info-help')].map(n=>n.getAttribute('aria-label')||n.dataset.lexTitle||'')")
        assert any(text.startswith(count) and "Formulae Rework is enabled." in text for text in helps), helps
        assert "requested runtime formulae are implemented" not in unlocked["master"], unlocked["master"]
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
        assert metrics["cards"] == len(rows), metrics
        assert metrics["scrollerFound"], metrics
        assert metrics["overflowY"] == "auto", metrics
        assert metrics["scrollable"] > 0, metrics
        assert metrics["lastBottom"] <= metrics["viewport"], metrics
        if len(sys.argv) > 1:
            output = Path(sys.argv[1])
            output.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(output / "formulae-scrolled.png"))
        # The subtab stays open while the owning switch is off, like
        # GFs -> Spellbook: it opens onto the formulae and the reason.
        locked = page.evaluate("""() => {
          state.data.settings.tweaks.find(row=>row.id==='formulae-rework').enabled = false;
          renderSettings();
          return {
            settingsTab: state.settingsTab,
            formulaCards: document.querySelectorAll('[data-formula-id]').length,
            text: document.querySelector('#main').textContent,
            helps: [...document.querySelectorAll('.lex-info-help')].map(n=>n.getAttribute('aria-label')||n.dataset.lexTitle||''),
            gameplay: !!document.querySelector('.lex-settings-columns') && document.querySelector('#main').textContent.includes('FLAT +STAT ABILITIES'),
            tweak: (() => { const input = document.querySelector('[aria-label="Formulae Rework"]');
              return input ? {disabled: input.disabled} : null; })(),
            subtabs: [...document.querySelectorAll('.lex-subtab-button')].map(button=>({
              label: button.querySelector('.lex-tab-label-text').textContent.trim(), disabled: button.disabled,
              active: button.classList.contains('active')})),
          };
        }""")
        assert not errors, errors
        assert locked["settingsTab"] == "formulae", locked
        assert locked["formulaCards"] == len(rows), locked
        assert any("Formulae Rework is disabled. The previews use the vanilla formulas." in text for text in locked["helps"]), locked
        assert "Formulae Rework is on" not in locked["text"], locked
        formulae_tab = next(tab for tab in locked["subtabs"] if tab["label"] == "Formulae")
        assert formulae_tab == {"label": "Formulae", "disabled": False, "active": True}, locked["subtabs"]
        if len(sys.argv) > 1:
            page.screenshot(path=str(Path(sys.argv[1]) / "formulae-disabled.png"))
        browser.close()
    print("PASS: Formulae tweaks subtab scrolls and stays open while its switch is off")
finally:
    server.shutdown()
    server.server_close()
    thread.join()
    fixture.cleanup()
