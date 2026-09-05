"""Sweep every plugin and every tab for text the layout is cutting off.

Lexer's question was not "nudge this one box" but "is there no way to prevent
this whole class of bug for good". Twenty-three verifiers already check
overflow, but each only on its own page, so a clip anywhere else ships
unnoticed. This one walks all plugins and all tabs and fails on any element
whose own text does not fit the box drawn for it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))
sys.path.insert(0, str(ROOT / "tools"))

from render_crime_editors_55_62 import Cdp, free_port, wait_eval, wait_json  # noqa: E402
from shot import EDGE, STUB, session_for  # noqa: E402
import browser_guard  # noqa: E402

# A scrollable region is allowed to be larger than its viewport; that is what
# scrolling is for. Only leaf text in a box that cannot scroll is a clip.
PROBE = r"""
(()=>{
  const bad=[];
  const scrollable=node=>{const cs=getComputedStyle(node);
    return /(auto|scroll)/.test(cs.overflowX+' '+cs.overflowY);};
  for(const node of document.querySelectorAll('*')){
    if(node.children.length) continue;
    const text=(node.textContent||'').trim();
    if(!text) continue;
    const cs=getComputedStyle(node);
    // display:none and visibility:hidden are skipped because they are not laid
    // out. opacity is NOT skipped: it does not affect layout at all, so a faded
    // hover-only surface measures exactly as it will when revealed. Skipping it
    // was the gap that let the hover drawers go unchecked.
    if(cs.display==='none'||cs.visibility==='hidden') continue;
    const r=node.getBoundingClientRect();
    if(r.width<2||r.height<2) continue;
    if(scrollable(node)) continue;
    // Deliberate single-line truncation is a designed affordance, not a bug.
    if(cs.textOverflow==='ellipsis') continue;
    // Text under overflow:visible SPILLS; it is still fully readable. Only a
    // box that actually clips can cut a glyph off, so that is what we flag.
    const clips=/(hidden|clip)/.test(cs.overflowX+' '+cs.overflowY);
    if(!clips) continue;
    const overW=/(hidden|clip)/.test(cs.overflowX)?node.scrollWidth-node.clientWidth:0;
    const overH=/(hidden|clip)/.test(cs.overflowY)?node.scrollHeight-node.clientHeight:0;
    // NOTE: this checks a box clipping its OWN text. Detecting an ANCESTOR
    // clipping a visible-overflow child was tried and removed: comparing
    // border-box rects over-reports badly (flex rows, centred children) and
    // produced 556 hits of which the ones checked by hand were all false -
    // a pager "cut off by 49px" was sitting well inside the viewport with no
    // clipping ancestor at all. Doing it properly needs the ancestor's client
    // area and per-axis intersection, not getBoundingClientRect.
    if(overW>1||overH>1){
      bad.push({text:text.slice(0,30),cls:String(node.className).slice(0,40),
                tag:node.tagName,overW,overH});
    }
  }
  return JSON.stringify(bad.slice(0,25));
})()
"""


def sweep(plugin: str, width: int, height: int) -> list[dict]:
    profile = tempfile.TemporaryDirectory(prefix="lex-clip-", ignore_cleanup_errors=True)
    project = tempfile.TemporaryDirectory(prefix="lex-clip-project-", ignore_cleanup_errors=True)
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    browser = None
    found: list[dict] = []
    try:
        with session_for(plugin, project.name) as session:
            port = free_port()
            browser = subprocess.Popen([
                str(EDGE), "--headless=new", "--no-first-run", "--no-default-browser-check",
                "--remote-allow-origins=*", "--use-angle=swiftshader",
                f"--remote-debugging-port={port}", f"--user-data-dir={profile.name}", "about:blank",
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=hidden)
            browser_guard.adopt(browser)
            page = next(value for value in wait_json(f"http://127.0.0.1:{port}/json/list")
                        if value.get("type") == "page")
            cdp = Cdp(page["webSocketDebuggerUrl"])
            cdp.call("Page.enable")
            cdp.call("Runtime.enable")
            cdp.call("Emulation.setDeviceMetricsOverride", {
                "width": width, "height": height, "deviceScaleFactor": 1, "mobile": False,
            })
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": STUB})
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state==='undefined'||!state.booting", 90)
            time.sleep(1.2)
            tabs = json.loads(cdp.eval(
                "JSON.stringify([...document.querySelectorAll('nav button[data-tab]')]"
                ".map(b=>b.dataset.tab))"))
            for tab in tabs or [None]:
                if tab:
                    cdp.eval(
                        "(()=>{const b=[...document.querySelectorAll('nav button[data-tab]')]"
                        f".find(x=>x.dataset.tab==={json.dumps(tab)});if(b)b.click();}})()")
                    time.sleep(.55)
                for entry in json.loads(cdp.eval(PROBE)):
                    entry["plugin"] = plugin
                    entry["tab"] = tab
                    entry["size"] = f"{width}x{height}"
                    found.append(entry)
    finally:
        browser_guard.kill_tree(browser)
    return found


def main() -> int:
    plugins = [p.name for p in sorted((ROOT / "games").iterdir())
               if (p / "editor.html").is_file()]
    clipped: list[dict] = []
    for plugin in plugins:
        for width, height in ((1600, 950), (1280, 720)):
            clipped.extend(sweep(plugin, width, height))
    print(json.dumps({"plugins": plugins, "clipped": len(clipped)}))
    if clipped:
        for entry in clipped[:20]:
            print(json.dumps(entry, ensure_ascii=True))
        raise AssertionError(f"{len(clipped)} clipped text boxes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
