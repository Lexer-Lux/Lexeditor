"""Headless rendered check for the FF8 managed-mod selector and load-order dialog."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))

from games.ff8 import runtime_layout  # noqa: E402
from games.ff8.plugin import FF8Session  # noqa: E402
from render_crime_editors_55_62 import Cdp, free_port, wait_eval, wait_json  # noqa: E402


def make_mod(root: Path, mod_id: str, name: str, order: int, enabled: bool,
             with_folder_option: bool = False) -> None:
    (root / "hext" / "ff8").mkdir(parents=True)
    (root / "hext" / "ff8" / "selector-test.txt").write_text(name, encoding="utf-8")
    (root / "mod.json").write_text(json.dumps({
        "id": mod_id, "name": name, "order": order, "enabled": enabled,
    }), encoding="utf-8")
    if with_folder_option:
        (root / "mod.xml").write_text(
            "<ModInfo><ConfigOption><Type>List</Type><Default>0</Default>"
            "<Name>Style</Name><ID>Style</ID>"
            "<Option Value=\"0\" Name=\"Classic\"/>"
            "<Option Value=\"1\" Name=\"Modern\"/>"
            "</ConfigOption><ModFolder Folder=\"modern\" ActiveWhen=\"Style = 1\"/>"
            "</ModInfo>", encoding="utf-8",
        )


def main() -> int:
    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    output = ROOT / "worklog" / "issues" / "rendered" / "goal-ff8-mod-load-order.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-mod-order-edge-", ignore_cleanup_errors=True)
    scratch = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-mod-order-render-", ignore_cleanup_errors=True)
    root = Path(scratch.name)
    project, mods, runtime = root / "editable", root / "mods", root / "runtime"
    make_mod(project, "editable", "My Editable Mod", 0, True)
    make_mod(mods / "red", "red", "Red Reference", 10, True, True)
    make_mod(mods / "blue", "blue", "Disabled Blue", 20, False)
    runtime_layout.compose(project, runtime, runtime_layout.catalog(project, mods))
    browser = None
    cdp = None
    port = free_port()
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        with FF8Session({
            "LEXEDITOR_FF8_PROJECT": str(project),
            "LEXEDITOR_FF8_MODS_ROOT": str(mods),
            "LEXEDITOR_FF8_RUNTIME_ROOT": str(runtime),
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
                "width": 1500, "height": 900, "deviceScaleFactor": 1, "mobile": False,
            })
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
              window.__testErrors=[];
              addEventListener('error',event=>{if(!String(event.message).includes('ResizeObserver loop'))window.__testErrors.push(String(event.message));});
              addEventListener('unhandledrejection',event=>window.__testErrors.push(String(event.reason)));
            """})
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting&&state.mods.rows.length===3", 90)
            cdp.eval("document.querySelector('.lex-project-select').click()")
            wait_eval(cdp, "!document.querySelector('.lex-project-menu').hidden", 10)
            geometry = cdp.eval("""(()=>{const trigger=document.querySelector('.lex-project-select').getBoundingClientRect(),menu=document.querySelector('.lex-project-menu').getBoundingClientRect(),center=document.querySelector('.lex-shell-center-actions').getBoundingClientRect();return{trigger:{left:trigger.left,right:trigger.right,width:trigger.width},menu:{left:menu.left,right:menu.right,width:menu.width},centerLeft:center.left,errors:window.__testErrors}})()""")
            assert abs(geometry["trigger"]["width"] - geometry["menu"]["width"]) <= 1, geometry
            assert geometry["trigger"]["right"] <= geometry["centerLeft"] - 6, geometry
            assert geometry["menu"]["right"] <= geometry["centerLeft"] - 6 and not geometry["errors"], geometry
            selector = cdp.eval("[...document.querySelectorAll('.lex-project-reference')].map(node=>({name:node.querySelector('.lex-project-menu-name')?.textContent,mode:node.querySelector('.lex-project-source-mode')?.textContent,status:node.querySelector('.lex-project-source-status')?.textContent}))")
            assert selector[:3] == [
                {"name": "Vanilla", "mode": "🔒", "status": "✓"},
                {"name": "My Editable Mod", "mode": "📝", "status": "✓"},
                {"name": "Red Reference", "mode": "🔒", "status": "✓"},
            ], selector
            closed = cdp.eval("""(()=>{const trigger=document.querySelector('.lex-project-select'),open=[...document.querySelectorAll('.lex-project-reference')].find(node=>node.classList.contains('active')),closedStatus=trigger.querySelector('.lex-project-source-status'),openStatus=open.querySelector('.lex-project-source-status'),closedRect=closedStatus.getBoundingClientRect(),openRect=openStatus.getBoundingClientRect();return{mode:trigger.querySelector('.lex-project-source-mode').textContent,status:closedStatus.textContent,closedColor:getComputedStyle(closedStatus).color,openColor:getComputedStyle(openStatus).color,closedCenter:closedRect.top+closedRect.height/2,triggerCenter:(()=>{const rect=trigger.getBoundingClientRect();return rect.top+rect.height/2})(),openOffset:(()=>{const row=open.getBoundingClientRect();return openRect.top+openRect.height/2-(row.top+row.height/2)})()}})()""")
            assert closed["mode"] == "📝" and closed["status"] == "✓", closed
            assert closed["closedColor"] == closed["openColor"], closed
            assert abs(closed["closedCenter"] - closed["triggerCenter"]) <= 1, closed
            assert abs(closed["openOffset"]) <= 1, closed
            assert not any("Disabled Blue" in value for value in selector), selector
            cdp.eval("[...document.querySelectorAll('.lex-project-menu-item-select')].find(node=>node.textContent.includes('Red Reference')).click()")
            wait_eval(cdp, "state.activeSource==='mod:red'&&document.documentElement.dataset.lexProjectReadonly==='true'", 30)
            cdp.eval("document.querySelector('.lex-project-select').click();[...document.querySelectorAll('.lex-project-menu-item-select')].find(node=>node.textContent.includes('My Editable Mod')).click()")
            wait_eval(cdp, "state.activeSource==='mine'&&document.documentElement.dataset.lexProjectReadonly==='false'", 30)
            cdp.eval("openModOrder()")
            wait_eval(cdp, "document.querySelectorAll('.ff8-mod-row').length===3", 10)
            assert cdp.eval("document.querySelector('[data-mod-id=\"red\"] .ff8-mod-folder-option').textContent.includes('Style')")
            assert cdp.eval("document.querySelector('[data-mod-id=\"red\"] .ff8-mod-folder-option select').value==='0'")
            cdp.eval("document.querySelector('[data-mod-id=\"red\"] .ff8-mod-folder-option select').value='1';document.querySelector('[data-mod-id=\"red\"] .ff8-mod-folder-option select').dispatchEvent(new Event('change',{bubbles:true}))")
            assert cdp.eval("[...document.querySelectorAll('.ff8-mod-order button')].some(node=>node.textContent.includes('Import IROJ'))")
            assert cdp.eval("document.querySelector('.ff8-featured-row').textContent.includes(\"Lexer's Mod\")")
            assert not cdp.eval("document.querySelector('.ff8-featured-row').textContent.includes(\"for FF8\")")
            assert cdp.eval("document.querySelector('.ff8-featured-row button').textContent==='Download Latest'")
            assert cdp.eval("document.querySelectorAll('.ff8-mod-row button[title^=\"Delete\"]').length===2")
            cdp.eval("document.querySelector('[data-mod-id=\"blue\"] button[title^=\"Delete\"]').click()")
            wait_eval(cdp, "document.querySelectorAll('.lex-dialog-backdrop').length===2", 10)
            assert cdp.eval("[...document.querySelectorAll('.lex-dialog-backdrop')].at(-1).textContent.includes('removes only this managed mod')")
            cdp.eval("[...document.querySelectorAll('.lex-dialog-backdrop')].at(-1).querySelector('button').click()")
            wait_eval(cdp, "document.querySelectorAll('.lex-dialog-backdrop').length===1", 10)
            before = cdp.eval("({rows:[...document.querySelectorAll('.ff8-mod-row')].map(row=>row.textContent.trim()),conflicts:document.querySelector('.ff8-mod-conflicts').textContent,errors:window.__testErrors})")
            assert "Winner: ordered runtime patches" in before["conflicts"] and "editable → red" in before["conflicts"], before
            assert not before["errors"], before
            # Move Red above the edit target. Hext keeps both files and changes
            # their deterministic low-to-high application order.
            cdp.eval("document.querySelector('[data-mod-id=\"red\"] .ff8-mod-move').click();document.querySelector('.ff8-mod-order .primary').click()")
            wait_eval(cdp, "document.querySelector('.ff8-mod-conflicts').textContent.includes('red → editable')", 20)
            persisted = cdp.eval("fetch('/api/mods').then(r=>r.json())", await_promise=True)
            assert [row["id"] for row in persisted["rows"]] == ["red", "editable", "blue"], persisted
            assert persisted["composition"]["conflicts"][0]["winner"] == "ordered runtime patches", persisted
            assert persisted["composition"]["conflicts"][0]["claimants"] == ["red", "editable"], persisted
            assert next(row for row in persisted["rows"] if row["id"] == "red")["folderOptions"] == {"Style": 1}
            screenshot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            output.write_bytes(base64.b64decode(screenshot["data"]))
            print(json.dumps({"selector": selector, "order": [row["id"] for row in persisted["rows"]], "screenshot": str(output)}))
        return 0
    finally:
        if cdp:
            cdp.close()
        if browser:
            browser.terminate()
            browser.wait(timeout=10)
        profile.cleanup()
        scratch.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
