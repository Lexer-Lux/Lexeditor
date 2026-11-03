"""Rendered contract for Control-key tab shortcut prompts (GitHub #42)."""

from __future__ import annotations

import os
import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plugins.ff8.plugin import FF8Session  # noqa: E402
from render_crime_editors_55_62 import Cdp, free_port, wait_eval, wait_json  # noqa: E402


EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def main() -> int:
    port = free_port()
    profile = tempfile.TemporaryDirectory(
        prefix="lexeditor-tab-shortcut-edge-", ignore_cleanup_errors=True)
    browser = subprocess.Popen([
        str(EDGE), "--headless=new", "--no-first-run",
        "--no-default-browser-check", "--remote-allow-origins=*",
        "--use-angle=swiftshader", f"--remote-debugging-port={port}",
        f"--user-data-dir={profile.name}", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    cdp = None
    project = None
    try:
        page = next(value for value in wait_json(
            f"http://127.0.0.1:{port}/json/list") if value.get("type") == "page")
        cdp = Cdp(page["webSocketDebuggerUrl"])
        cdp.call("Page.enable")
        cdp.call("Runtime.enable")
        cdp.call("Emulation.setDeviceMetricsOverride", {
            "width": 1600, "height": 900, "deviceScaleFactor": 1, "mobile": False,
        })
        project = tempfile.TemporaryDirectory(
            prefix="lexeditor-tab-shortcut-project-", ignore_cleanup_errors=True)
        Path(project.name, "mod.json").write_text(json.dumps({
            "id": "shortcut-test", "name": "Shortcut Test",
            "enabled": True, "order": 0,
        }), encoding="utf-8")
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
              window.pywebview={api:{
                mod_projects:async()=>({canCreate:true,projects:[{name:'Shortcut Test',path:'Rendered test project',valid:true,current:true}]}),
                set_dirty_count:async()=>null,
                game_process_status:async()=>null
              }};
            """})
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
            wait_eval(cdp, "!document.documentElement.classList.contains('lex-loading-live')", 15)
            cdp.eval("document.fonts.ready.then(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))))", True)
            if not cdp.eval("!!document.querySelector('.lex-shell-header')"):
                snapshot = cdp.eval("""(()=>({title:document.title,body:document.body.innerText.slice(0,1000),
                  html:document.body.innerHTML.slice(0,1500),errors:window.__testErrors||[]}))()""")
                raise AssertionError(f"The mounted page has no shared shell: {snapshot}")
            if not cdp.eval("!!document.querySelector('nav button[data-tab]')"):
                snapshot = cdp.eval("""(()=>({html:document.querySelector('.lex-shell-header')?.outerHTML,
                  buttons:[...document.querySelectorAll('button')].map(n=>({id:n.id,tab:n.dataset.tab,text:n.textContent}))}))()""")
                raise AssertionError(f"The mounted shell has no tab buttons: {snapshot}")
            shortcut_count = cdp.eval("document.querySelectorAll('nav button[data-tab] .lex-tab-shortcut').length")
            if not shortcut_count:
                raise AssertionError("The mounted shared tabs have no shortcut prompts")
            before = cdp.eval("""(()=>{const button=document.querySelector('nav button[data-tab]'),
              badge=button.querySelector('.lex-tab-shortcut'),label=button.querySelector('.lex-tab-label'),
              b=button.getBoundingClientRect(),l=label.getBoundingClientRect(),s=getComputedStyle(badge),bs=getComputedStyle(button);
              return{visibility:s.visibility,opacity:s.opacity,button:{left:b.left,right:b.right},
                label:{left:l.left,right:l.right,center:(l.left+l.right)/2},
                center:(b.left+parseFloat(bs.borderLeftWidth)+b.right-parseFloat(bs.borderRightWidth))/2};})()""")
            box = cdp.eval("""(()=>{const r=document.querySelector('nav button[data-tab]').getBoundingClientRect();
              return{x:r.left+r.width/2,y:r.top+r.height/2};})()""")
            cdp.call("Input.dispatchMouseEvent", {
                "type": "mouseMoved", "x": box["x"], "y": box["y"], "buttons": 0,
            })
            try:
                # Input delivery and :hover style updates complete on a frame;
                # a CDP response alone does not prove that frame has painted.
                wait_eval(cdp, "document.querySelector('nav button[data-tab]').matches(':hover')", 5)
            except Exception:
                hit = cdp.eval(f"document.elementFromPoint({box['x']},{box['y']})?.outerHTML")
                raise AssertionError(f"Pointer did not reach the first tab at {box}: {hit}")
            assert cdp.eval("getComputedStyle(document.querySelector('nav button[data-tab] .lex-tab-shortcut')).visibility") == "hidden", "hover alone must not reveal keyboard shortcuts"
            cdp.call("Input.dispatchKeyEvent", {"type":"rawKeyDown","key":"Control","code":"ControlLeft","windowsVirtualKeyCode":17,"modifiers":2})
            wait_eval(cdp, "getComputedStyle(document.querySelector('nav button[data-tab] .lex-tab-shortcut')).visibility==='visible'&&parseFloat(getComputedStyle(document.querySelector('nav button[data-tab] .lex-tab-shortcut')).opacity)>.95", 5)
            hovered = cdp.eval("""(()=>{const button=document.querySelector('nav button[data-tab]'),
              badge=button.querySelector('.lex-tab-shortcut'),label=button.querySelector('.lex-tab-label'),
              b=button.getBoundingClientRect(),l=label.getBoundingClientRect(),r=badge.getBoundingClientRect(),
              s=getComputedStyle(badge),bs=getComputedStyle(button);return{visibility:s.visibility,opacity:parseFloat(s.opacity),
                label:{left:l.left,right:l.right},
                leftInset:l.left-b.left-parseFloat(bs.borderLeftWidth),rightInset:b.right-l.right-parseFloat(bs.borderRightWidth),
                badgeInside:r.left>=b.left&&r.right<=b.right};})()""")
            cdp.call("Input.dispatchMouseEvent", {
                "type": "mouseMoved", "x": 1595, "y": 895, "buttons": 0,
            })
            assert cdp.eval("getComputedStyle(document.querySelector('nav button[data-tab] .lex-tab-shortcut')).visibility") == "visible", "Control prompts must remain visible away from the tab"
            cdp.call("Input.dispatchKeyEvent", {"type":"keyUp","key":"Control","code":"ControlLeft","windowsVirtualKeyCode":17,"modifiers":0})
            wait_eval(cdp, "getComputedStyle(document.querySelector('nav button[data-tab] .lex-tab-shortcut')).visibility==='hidden'", 5)
            after = cdp.eval("getComputedStyle(document.querySelector('nav button[data-tab] .lex-tab-shortcut')).visibility")

        assert before["visibility"] == "hidden" and float(before["opacity"]) == 0
        assert abs(before["label"]["center"] - before["center"]) <= 0.5, before
        assert hovered["visibility"] == "visible" and hovered["opacity"] > 0
        # Control prompts overlay the tabs; they must not reserve label space
        # or change its geometry. Game themes can use asymmetric edge borders.
        assert hovered["badgeInside"], hovered
        assert hovered["label"] == {key:before["label"][key] for key in ("left","right")}, (before,hovered)
        assert abs(hovered["leftInset"] - hovered["rightInset"]) <= 0.5
        assert after == "hidden"
        print({"hiddenAtRest": True, "hiddenOnHover": True, "visibleWithControl": True,
               "labelCenteredInContent": True, "labelGeometryUnchanged": True})
        return 0
    finally:
        if cdp is not None:
            cdp.close()
        browser.terminate()
        browser.wait(timeout=10)
        profile.cleanup()
        if project:
            project.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
