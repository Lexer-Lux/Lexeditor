"""Hidden Edge acceptance for RDR2 typed hoverables (GitHub #45)."""

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

from games.rdr2.plugin import Rdr2Session  # noqa: E402
from render_crime_editors_55_62 import Cdp, free_port, wait_eval, wait_json  # noqa: E402


def point(cdp: Cdp, selector: str) -> tuple[float, float]:
    box = cdp.eval(f"""(()=>{{const r=document.querySelector({selector!r}).getBoundingClientRect();return {{x:r.left+r.width/2,y:r.top+r.height/2}}}})()""")
    return box["x"], box["y"]


def mouse(cdp: Cdp, selector: str, modifiers: int = 0, click: bool = True) -> None:
    cdp.eval(f"document.querySelector({selector!r}).scrollIntoView({{block:'center',inline:'center'}})")
    x, y = point(cdp, selector)
    cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y, "modifiers": modifiers})
    if click:
        cdp.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y,
                                                "button": "left", "clickCount": 1, "modifiers": modifiers})
        cdp.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y,
                                                "button": "left", "clickCount": 1, "modifiers": modifiers})


def main() -> int:
    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    output = ROOT / "worklog" / "issues" / "rendered" / "github-45-rdr2-loot-hoverable.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-rdr2-hoverables-edge-", ignore_cleanup_errors=True)
    port = free_port()
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    browser = None
    cdp = None
    item_selector = '.entrygrid .lex-hoverable[data-hover-target-type="rdr2-item"]'
    table_selector = '.entrygrid .lex-hoverable[data-hover-target-type="rdr2-loot-table"]'
    try:
        with Rdr2Session() as session:
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
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
              window.__testErrors=[];
              addEventListener('error',event=>{if(String(event.message).indexOf('ResizeObserver loop')>=0)return;window.__testErrors.push(String(event.message));});
              addEventListener('unhandledrejection',event=>window.__testErrors.push(String(event.reason)));
            """})
            cdp.call("Emulation.setDeviceMetricsOverride", {
                "width": 1600, "height": 900, "deviceScaleFactor": 1, "mobile": False,
            })
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting&&!!state.catalog", 120)
            cdp.eval("window.dispatchEvent(new CustomEvent('lexeditor-settings-changed',{detail:{hoverableAltClick:false,developerMode:false,viewPreferences:{}}}))")

            cdp.eval("navigate('crafting')")
            craft_selector = '.craft-detail-pane .ingredient-row .lex-hoverable[data-hover-target-type="rdr2-item"]'
            wait_eval(cdp, f"!!document.querySelector({craft_selector!r})", 60)
            craft_item = cdp.eval(f"document.querySelector({craft_selector!r}).dataset.hoverTargetId")
            mouse(cdp, craft_selector)
            wait_eval(cdp, f"state.tab==='items'&&state.filters.itemSel==={craft_item!r}", 45)

            cdp.eval("""(async()=>{
              const file='loot_table_itemgroups.meta';await loadLoot(file);state.lootFile=file;
              const direct=state.loot[file].tables.find(t=>t.entries.some(e=>e.type!=='Table'&&catalogItem(e.name)));
              state.filters.lootSel=direct.key;state.filters.lootQ=direct.key;state.filters.lootPage=0;await renderLoot();
            })()""", True)
            wait_eval(cdp, f"!!document.querySelector({item_selector!r})", 60)
            loot_item = cdp.eval(f"document.querySelector({item_selector!r}).dataset.hoverTargetId")
            before = cdp.eval(f"getComputedStyle(document.querySelector({item_selector!r})).color")
            mouse(cdp, item_selector, click=False)
            wait_eval(cdp, f"getComputedStyle(document.querySelector({item_selector!r})).textDecorationLine==='underline'", 5)
            after = cdp.eval(f"(()=>{{const style=getComputedStyle(document.querySelector({item_selector!r}));return{{color:style.color,decoration:style.textDecorationLine}}}})()")
            hover_state = cdp.eval(f"document.querySelector({item_selector!r}).matches(':hover')")
            hover_debug = cdp.eval(f"""(()=>{{
              const el=document.querySelector({item_selector!r});
              const style=getComputedStyle(el);
              return {{
                classes:el.className,
                highlight:style.getPropertyValue('--lex-highlight'),
                borderStyle:style.borderStyle,
                borderWidth:style.borderWidth,
                background:style.backgroundColor,
                boxShadow:style.boxShadow,
                rules:[...document.styleSheets].flatMap(sheet=>{{
                  try {{ return [...sheet.cssRules]; }} catch (_) {{ return []; }}
                }}).filter(rule=>rule.selectorText&&el.matches(rule.selectorText)&&
                  (rule.style.border||rule.style.borderColor||rule.style.boxShadow)).map(rule=>({{
                    selector:rule.selectorText,border:rule.style.border,borderColor:rule.style.borderColor,
                    boxShadow:rule.style.boxShadow,cssText:rule.cssText
                  }})),
              }};
            }})()""")
            assert hover_state and after["decoration"] == "underline", {
                "before": before, "after": after, "hover": hover_state, **hover_debug,
            }
            shot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            output.write_bytes(base64.b64decode(shot["data"]))
            mouse(cdp, item_selector)
            wait_eval(cdp, f"state.tab==='items'&&state.filters.itemSel==={loot_item!r}", 45)

            cdp.eval("""(async()=>{
              window.dispatchEvent(new CustomEvent('lexeditor-settings-changed',{detail:{hoverableAltClick:true,developerMode:false,viewPreferences:{}}}));
              const file='loot_table_itemgroups.meta';await loadLoot(file);state.lootFile=file;
              const direct=state.loot[file].tables.find(t=>t.entries.some(e=>e.type!=='Table'&&catalogItem(e.name)));
              state.filters.lootSel=direct.key;state.filters.lootQ=direct.key;state.filters.lootPage=0;state.tab='loot';await renderLoot();
            })()""", True)
            wait_eval(cdp, f"!!document.querySelector({item_selector!r})", 60)
            source_table = cdp.eval("state.filters.lootSel")
            mouse(cdp, item_selector)
            assert cdp.eval("state.tab") == "loot" and cdp.eval("state.filters.lootSel") == source_table
            mouse(cdp, item_selector, modifiers=1)
            wait_eval(cdp, f"state.tab==='items'&&state.filters.itemSel==={loot_item!r}", 45)

            cdp.eval("""(async()=>{
              window.dispatchEvent(new CustomEvent('lexeditor-settings-changed',{detail:{hoverableAltClick:false,developerMode:false,viewPreferences:{}}}));
              const file='loot_table_itemgroups.meta';await loadLoot(file);state.lootFile=file;
              const parent=state.loot[file].tables.find(t=>t.entries.some(e=>e.type==='Table'&&findLootTable(e.name)));
              state.filters.lootSel=parent.key;state.filters.lootQ=parent.key;state.filters.lootPage=0;state.tab='loot';await renderLoot();
            })()""", True)
            wait_eval(cdp, f"!!document.querySelector({table_selector!r})", 60)
            target = cdp.eval(f"document.querySelector({table_selector!r}).dataset.hoverTargetId")
            mouse(cdp, table_selector)
            target_file, target_key = target.split("|", 1)
            wait_eval(cdp, f"state.tab==='loot'&&state.lootFile==={target_file!r}&&state.filters.lootSel==={target_key!r}", 45)
            result = cdp.eval("""(()=>({
              item:state.filters.itemSel,lootFile:state.lootFile,lootTable:state.filters.lootSel,
              typed:document.querySelectorAll('.lex-hoverable[data-hover-target-type][data-hover-target-id]').length,
              errors:window.__testErrors,
            }))()""")
            assert result["typed"] > 0 and not result["errors"], result
            print({"craftItem": craft_item, "lootItem": loot_item, "nested": target, "hover": [before, after], "result": result})
        return 0
    finally:
        if cdp:
            cdp.close()
        if browser:
            browser.terminate()
            browser.wait(timeout=10)
        profile.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
