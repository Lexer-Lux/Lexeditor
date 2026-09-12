"""Hidden rendered check for the FF8 gameplay settings in issue 50."""

from __future__ import annotations

import base64
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))

from games.ff8.plugin import FF8Session  # noqa: E402
from render_crime_editors_55_62 import Cdp, free_port, wait_eval, wait_json  # noqa: E402


def main() -> int:
    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    output = ROOT / "worklog" / "issues" / "rendered" / "github-50-ff8-settings.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-settings-edge-", ignore_cleanup_errors=True)
    project = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-settings-project-", ignore_cleanup_errors=True)
    runtime = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-settings-runtime-", ignore_cleanup_errors=True)
    port = free_port()
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    browser = None
    cdp = None
    try:
        with FF8Session({
            "LEXEDITOR_FF8_PROJECT": project.name,
            "LEXEDITOR_FF8_RUNTIME_ROOT": runtime.name,
        }) as session:
            browser = subprocess.Popen([
                str(edge), "--headless=new", "--no-first-run", "--no-default-browser-check",
                "--remote-allow-origins=*", "--use-angle=swiftshader",
                f"--remote-debugging-port={port}", f"--user-data-dir={profile.name}", "about:blank",
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=hidden)
            page = next(value for value in wait_json(f"http://127.0.0.1:{port}/json/list")
                        if value.get("type") == "page")
            cdp = Cdp(page["webSocketDebuggerUrl"])
            cdp.call("Page.enable")
            cdp.call("Runtime.enable")
            cdp.call("Emulation.setDeviceMetricsOverride", {
                "width": 1600, "height": 900, "deviceScaleFactor": 1, "mobile": False,
            })
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
              window.__testErrors=[];
              addEventListener('error',event=>{if(String(event.message).indexOf('ResizeObserver loop')>=0)return;window.__testErrors.push(String(event.message));});
              addEventListener('unhandledrejection',event=>window.__testErrors.push(String(event.reason)));
            """})
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
            cdp.eval("navigate('settings')")
            # Wait for the page to be built, not for a particular number of
            # settings. Pinning the count made every new gameplay setting break
            # this check, which is the opposite of what it is here to catch.
            wait_eval(cdp, "state.tab==='settings'&&document.querySelectorAll('.setting-row').length>0"
                           "&&!!document.querySelector('[aria-label=\"Monogamy\"]')", 30)
            result = cdp.eval("""(()=>({
              labels:[...document.querySelectorAll('.setting-copy strong')].map(node=>node.textContent),
              toolbar:(()=>{const toolbar=document.querySelector('#toolbar'),save=document.querySelector('#global-save'),badge=save?.querySelector('.lex-save-count');return{hidden:toolbar.hidden,localSave:!!toolbar.querySelector('.lex-settings-save-control'),globalSave:!!save,disabled:save?.disabled,badgeHidden:badge?.hidden}})(),
              headings:[...document.querySelectorAll('.settings-view h1,.settings-view h2')].map(node=>node.textContent.trim()),
              singleGf:{type:document.querySelector('[aria-label="Monogamy"]').type,checked:document.querySelector('[aria-label="Monogamy"]').checked},
              lexerDefaults:document.querySelectorAll('.lex-setting-default-control').length,
              booleans:[...document.querySelectorAll('.setting-control.boolean input[type="checkbox"]')].map(node=>{const box=node.getBoundingClientRect(),parent=node.closest('.setting-row').getBoundingClientRect();return{label:node.getAttribute('aria-label'),type:node.type,disabled:node.disabled,inside:box.left>=parent.left&&box.top>=parent.top&&box.right<=parent.right&&box.bottom<=parent.bottom}}),
              flying:(()=>{const enabled=document.querySelector('[aria-label="Enable Flying EVA Bonus"]'),value=document.querySelector('[aria-label="Flying EVA Bonus"]');return{enabled:!!enabled,value:!!value,checked:enabled?.checked}})(),
              removed:["Formulae Rework"].filter(label=>document.querySelector(`[aria-label="${label}"]`)),
              errors:window.__testErrors
            }))()""")
            # This check is about the shape of the settings page, not its
            # contents: which settings FF8 offers is Lexer's to change, and it
            # has grown since this was written. So it asks that the settings
            # issue 50 was about are still here, that every switch is a real
            # checkbox drawn inside its own row, and that no Lexer-scope
            # default control leaked onto a game page.
            required = [
                "MONOGAMY", "FAST START", "AUTO-SORT INVENTORY",
                "AUTO-SORT MAGIC MENU", "ENHANCED ABILITY MENU",
                "UNIVERSAL ITEM", "ENHANCED SCAN", "SHARED PARTY MAGIC INVENTORY",
                "MAX SPELL", "FLAT +STAT ABILITIES",
                "COMMAND MENU REWORK", "FF10-STYLE PARTY SWITCH",
                "DRAW ONCE PER ENEMY", "STREAMLINED DRAW", "TRUE ATB WAIT",
                "BETTER CARD", "BETTER TARGETING", "REMOVE DAMAGE LIMIT",
                "XP BARS", "HP BARS", "MODERN CONTROLS",
                "VIBRATION RATIONALIZATION", "FLYING EVA BONUS",
            ]
            missing = [label for label in required if label not in result["labels"]]
            assert not missing, (missing, result["labels"])
            # Order still matters where it was deliberate: the settings above
            # must keep their relative sequence even as new ones appear between
            # them, because the page is read top to bottom.
            positions = [result["labels"].index(label) for label in required]
            assert positions == sorted(positions), (required, result["labels"])
            assert result["toolbar"] == {
                "hidden": False, "localSave": False, "globalSave": True,
                "disabled": True, "badgeHidden": True,
            }, result
            assert result["headings"] == [], result
            assert result["singleGf"] == {"type": "checkbox", "checked": False}, result
            assert result["lexerDefaults"] == 0, result
            escaped = [entry for entry in result["booleans"] if not entry["inside"]]
            assert not escaped, escaped
            wrong_type = [entry for entry in result["booleans"] if entry["type"] != "checkbox"]
            assert not wrong_type, wrong_type
            switches = {entry["label"] for entry in result["booleans"]}
            for label in ("Monogamy", "Fast Start", "Universal Item", "Better Card",
                          "Remove Damage Limit", "Modern Controls"):
                assert label in switches, (label, sorted(switches))
            assert result["flying"] == {"enabled": True, "value": True, "checked": False}, result
            assert result["removed"] == [], result
            assert not result["errors"], result
            cdp.eval("document.querySelector('[aria-label=\"Monogamy\"]').click()")
            wait_eval(cdp, "!document.querySelector('#global-save').disabled", 5)
            cdp.eval("""document.querySelector('#global-save').dispatchEvent(
                new MouseEvent('contextmenu',{bubbles:true,cancelable:true,button:2}))""")
            wait_eval(cdp, "!!document.querySelector('.lex-discard-dialog')", 5)
            discard = cdp.eval("""(() => ({
              dirty:dirtyCount(), saveDisabled:document.querySelector('#global-save').disabled,
              badge:document.querySelector('#global-save .lex-save-count').textContent,
              title:document.querySelector('.lex-discard-dialog h2').textContent.trim(),
              actions:[...document.querySelectorAll('.lex-discard-dialog .lex-dialog-action')].map(node=>node.textContent.trim()),
            }))()""")
            assert discard == {
                "dirty": 1, "saveDisabled": False, "badge": "1", "title": "Discard unsaved changes?",
                "actions": ["Cancel", "Discard Changes"],
            }, discard
            cdp.eval("[...document.querySelectorAll('.lex-discard-dialog .lex-dialog-action')].find(node=>node.textContent.trim()==='Discard Changes').click()")
            wait_eval(cdp, "dirtyCount()===0&&!document.querySelector('.lex-discard-dialog')", 5)
            restored = cdp.eval("""(() => ({
              checked:document.querySelector('[aria-label="Monogamy"]').checked,
              saveDisabled:document.querySelector('#global-save').disabled,
              badgeHidden:document.querySelector('#global-save .lex-save-count').hidden,
              errors:window.__testErrors,
            }))()""")
            assert restored == {"checked": False, "saveDisabled": True, "badgeHidden": True, "errors": []}, restored
            cdp.eval("document.querySelector('[aria-label=\"Monogamy\"]').click()")
            wait_eval(cdp, "!document.querySelector('#global-save').disabled", 5)
            cdp.eval("document.querySelector('#global-save').click()")
            wait_eval(cdp, "state.base.settings.singleGf===true&&dirtyCount()===0&&document.querySelector('#global-save').disabled", 15)
            saved = cdp.eval("""(() => ({
              checked:document.querySelector('[aria-label="Monogamy"]').checked,
              base:state.base.settings.singleGf,
              saveDisabled:document.querySelector('#global-save').disabled,
              badgeHidden:document.querySelector('#global-save .lex-save-count').hidden,
              errors:window.__testErrors,
            }))()""")
            assert saved == {"checked": True, "base": True, "saveDisabled": True, "badgeHidden": True, "errors": []}, saved
            screenshot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            output.write_bytes(base64.b64decode(screenshot["data"]))
            print(result)
        return 0
    finally:
        if cdp:
            cdp.close()
        if browser:
            browser.terminate()
            browser.wait(timeout=10)
        project.cleanup()
        runtime.cleanup()
        profile.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
