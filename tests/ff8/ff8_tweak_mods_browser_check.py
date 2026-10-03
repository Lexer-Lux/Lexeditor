"""The Tweaks page lists tweak mods from their schemas, edits them and saves them.

Runs against a temporary project with its own small tweak-mod library, so it
never reads or changes the reader's real mod library or trust list.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core import script_mods  # noqa: E402
from plugins.ff8.plugin import FF8Session  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

TWEAK = '''
def build(settings, context):
    return {context.HEXT + "/%s.txt": "# %s\\n" + "".join(f"# {k}={v}\\n" for k, v in sorted(settings.items()))}
'''


def make(library: Path, mod_id: str, name: str, order: int, schema: dict, enabled: bool) -> Path:
    root = library / name
    (root / "script").mkdir(parents=True)
    (root / "script" / "__init__.py").write_text("", encoding="utf-8")
    (root / "script" / "tweak.py").write_text(TWEAK % (mod_id, name), encoding="utf-8")
    (root / "settings.schema.json").write_text(json.dumps(schema), encoding="utf-8")
    (root / "mod.json").write_text(json.dumps({"id": mod_id, "name": name, "order": order,
                                               "enabled": enabled, "script": {"version": 1}}), encoding="utf-8")
    return root


def main(output: Path | None = None) -> int:
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff8-tweak-mods-", ignore_cleanup_errors=True) as temp:
        temp = Path(temp)
        project = temp / "project"
        library = project / ".lexeditor-mods"
        os.environ[script_mods.TRUST_ENV] = str(temp / "trust.json")
        base = make(library, "base-tweak", "Base Tweak", 100, {
            "title": "BASE TWEAK", "help": "A tweak another one needs.", "fields": [
                {"key": "amount", "label": "Amount", "type": "int", "default": 5, "min": 0, "max": 50, "unit": "%"}]}, True)
        dependent = make(library, "dependent-tweak", "Dependent Tweak", 110, {
            "title": "DEPENDENT TWEAK", "help": "Needs Base Tweak.", "requires": ["base-tweak"], "fields": [
                {"key": "loud", "label": "Loud", "type": "bool", "default": False}]}, True)
        unfinished = make(library, "unfinished-tweak", "Unfinished Tweak", 120, {
            "title": "UNFINISHED TWEAK", "help": "Not ready.", "blocker": "Its hooks are not proved yet."}, False)
        for root in (base, dependent, unfinished):
            script_mods.set_trusted(root, True)
        untrusted = make(library, "stranger-tweak", "Stranger Tweak", 130, {"title": "STRANGER TWEAK", "help": "From elsewhere."}, False)
        casting = make(library, "gf-hp-casting", "GF HP Casting", 140, {
            "title": "GF HP CASTING", "fields": [
                {"key": "costs", "label": "GF HP costs", "type": "intList", "length": 57,
                 "default": [0] * 57, "min": 0, "max": 9999, "hidden": True}]}, True)
        script_mods.set_trusted(casting, True)
        errors: list[str] = []
        with FF8Session({"LEXEDITOR_FF8_PROJECT": str(project), script_mods.TRUST_ENV: str(temp / "trust.json")}) as session:
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True, args=["--mute-audio"])
                try:
                    page = browser.new_page(viewport={"width": 1400, "height": 900})
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_function("()=>typeof state!=='undefined'&&!state.booting", timeout=180000)
                    page.wait_for_function("()=>!document.documentElement.classList.contains('lex-loading-live')")
                    page.evaluate("()=>{state.settingsTab='gameplay';navigate('settings')}")
                    page.get_by_text("BASE TWEAK", exact=True).wait_for()
                    # GF Spellbooks and Shared Party Magic Inventory are tweak
                    # mods now, so they are only here when the library has them.
                    for title in ("DEPENDENT TWEAK", "UNFINISHED TWEAK", "STRANGER TWEAK"):
                        page.get_by_text(title, exact=True).wait_for()
                    # A tweak is a mod: the Mods tab switches it, so here
                    # there is no switch, only an OFF mark on a disabled one.
                    assert page.get_by_role("checkbox", name="Base Tweak").count() == 0
                    assert page.locator(".lex-tweak-off").count() == 2
                    page.get_by_text("NOT AVAILABLE YET").first.wait_for()
                    page.get_by_role("button", name="Trust this tweak").wait_for()
                    if output:
                        page.locator('.lex-plugin-loading-screen').wait_for(state='detached')
                        page.screenshot(path=str(output / "tweak-mods.png"), full_page=True)
                    amount = page.get_by_role("spinbutton", name="Amount")
                    amount.fill("12")
                    amount.press("Tab")
                    page.get_by_role("checkbox", name="Loud").check()
                    # A tweak's values save to its mod at once: no Save, and
                    # nothing pending in the open project.
                    page.wait_for_function("()=>{const base=state.base.settings.tweaks;return base.find(r=>r.id==='base-tweak').values.amount===12&&base.find(r=>r.id==='dependent-tweak').values.loud===true}", timeout=120000)
                    assert page.evaluate("()=>dirtyCount()") == 0
                    # Vanilla shows the same page, still editable: the
                    # values belong to the library, not the open mod.
                    page.evaluate("()=>{state.activeSource='vanilla';navigate('settings')}")
                    page.get_by_text("BASE TWEAK", exact=True).wait_for()
                    assert page.get_by_role("spinbutton", name="Amount").is_enabled()
                    page.evaluate("()=>{state.activeSource='mine';navigate('settings')}")
                    # Trust is applied at once, not saved with the page.
                    page.get_by_role("button", name="Trust this tweak").click()
                    page.wait_for_function("()=>state.data.settings.tweaks.find(r=>r.id==='stranger-tweak').trust==='trusted'")
                    page.reload()
                    page.wait_for_function("()=>typeof state!=='undefined'&&!state.booting", timeout=180000)
                    page.wait_for_function("()=>!document.documentElement.classList.contains('lex-loading-live')")
                    page.evaluate("()=>{state.settingsTab='gameplay';navigate('settings')}")
                    page.get_by_text("DEPENDENT TWEAK", exact=True).wait_for()
                    assert page.get_by_role("spinbutton", name="Amount").input_value() == "12"
                    if output:
                        page.locator('.lex-plugin-loading-screen').wait_for(state='detached')
                        page.screenshot(path=str(output / "tweak-mods-saved.png"), full_page=True)
                    page.evaluate("()=>{state.selected.magic=1;state.magicDetailTab='attack';navigate('magic')}")
                    cost = page.locator('input[aria-label^="GF HP cost for "]')
                    cost.wait_for()
                    assert cost.get_attribute("min") == "0" and cost.get_attribute("max") == "9999"
                    cost.fill("321")
                    cost.press("Tab")
                    page.evaluate("()=>saveAll()")
                    page.wait_for_function("()=>state.base.settings.tweaks.find(r=>r.id==='gf-hp-casting').values.costs[1]===321")
                    page.reload()
                    page.wait_for_function("()=>typeof state!=='undefined'&&!state.booting", timeout=180000)
                    page.wait_for_function("()=>!document.documentElement.classList.contains('lex-loading-live')")
                    page.evaluate("()=>{state.selected.magic=1;state.magicDetailTab='attack';navigate('magic')}")
                    assert cost.input_value() == "321"
                    if output:
                        page.locator('.lex-plugin-loading-screen').wait_for(state='detached')
                        page.screenshot(path=str(output / "magic-cost.png"), full_page=True)
                        page.set_viewport_size({"width": 1000, "height": 800})
                        page.wait_for_timeout(250)
                        page.screenshot(path=str(output / "magic-cost-small.png"), full_page=True)
                    page.evaluate("()=>{tweakMod('gf-hp-casting').enabled=false;renderAbilities()}")
                    assert cost.count() == 0
                finally:
                    browser.close()
        built = (base / "hext/ff8/en_nv/base-tweak.txt").read_text(encoding="utf-8")
        assert "amount=12" in built, built
        assert (dependent / "hext/ff8/en_nv/dependent-tweak.txt").read_text(encoding="utf-8").count("loud=True") == 1
        assert script_mods.trust_state(untrusted) == "trusted"
        assert json.loads((dependent / "mod.json").read_text(encoding="utf-8"))["enabled"] is True
        assert script_mods.values(casting)["costs"][1] == 321
        assert not errors, errors
    print(json.dumps({"tweakMods": 5, "noSwitch": True, "savedAndRebuilt": True, "trusted": True,
                      "magicCostSavedReloaded": True, "magicCostHiddenWhenDisabled": True}))
    return 0


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if out:
        out.mkdir(parents=True, exist_ok=True)
    raise SystemExit(main(out))
