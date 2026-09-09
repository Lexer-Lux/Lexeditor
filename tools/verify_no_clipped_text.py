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
    // SVG elements have no CSS box: clientWidth/scrollWidth read 0 and the
    // whole text width then looks like overflow. SVG clipping is governed by
    // the viewBox, which this sweep does not model.
    if(node.ownerSVGElement || node.tagName==='svg') continue;
    const r=node.getBoundingClientRect();
    if(r.width<2||r.height<2) continue;
    if(scrollable(node)) continue;
    // Deliberate single-line truncation is a designed affordance, not a bug -
    // but only where the property can actually take effect. text-overflow does
    // nothing on a flex or grid container, and nothing without nowrap, so a box
    // that merely DECLARES ellipsis can still hard-clip its text at both ends.
    // Trusting the declaration is what let centred table cells lose the start
    // of every long identifier while this sweep reported zero clipping.
    const ellipsisApplies = cs.textOverflow==='ellipsis'
      && !/(flex|grid)/.test(cs.display)
      && cs.whiteSpace!=='normal';
    if(ellipsisApplies) continue;
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


# A list of records without a pager is a list the user cannot page or search.
# Plugins kept hand-rolling a private search box above a bare column list, which
# looks fine on screen and silently caps the view at one page of data.
PAGER_PROBE = r"""
(()=>{
  const bad=[];
  for(const list of document.querySelectorAll('.lex-column-list')){
    const rows=list.querySelectorAll('.lex-column-list-row').length;
    if(!rows) continue;
    // Only a record list needs paging. columnList marks rows aria-selected
    // only when it drives a selection, so an editable reference grid (GF
    // compatibility, new-game party) has none and is skipped.
    if(!list.querySelector('[aria-selected]')) continue;
    const host=list.closest('.lex-paged-list-detail');
    if(host&&host.querySelector('.lex-pager')) continue;
    bad.push({cls:String(list.className).slice(0,60),rows,
              label:list.getAttribute('aria-label')||''});
  }
  return JSON.stringify(bad.slice(0,10));
})()
"""


# A tab that renders nothing looks like a styling problem and is not one. Every
# FF7R tab went blank at once because a helper read .content off a function that
# returns the element itself, and no check noticed.
EMPTY_PROBE = r"""
(()=>{
  const main=document.querySelector('#main,.lex-shell-main,main');
  if(!main) return JSON.stringify([{reason:'no main region'}]);
  const box=main.getBoundingClientRect();
  if(box.height<40) return JSON.stringify([]);
  const meaningful=[...main.querySelectorAll('*')].some(node=>{
    if(!(node.textContent||'').trim()) return false;
    const cs=getComputedStyle(node);
    if(cs.display==='none'||cs.visibility==='hidden') return false;
    const r=node.getBoundingClientRect();
    return r.width>2&&r.height>2;
  });
  if(meaningful) return JSON.stringify([]);
  return JSON.stringify([{reason:'tab renders no visible content',
                          height:Math.round(box.height)}]);
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
                # Data arrives asynchronously; a tab measured mid-load looks
                # empty. Only a tab still empty after a second wait counts.
                empty_hits = json.loads(cdp.eval(EMPTY_PROBE))
                if empty_hits:
                    time.sleep(2.5)
                    empty_hits = json.loads(cdp.eval(EMPTY_PROBE))
                for entry in empty_hits:
                    entry["plugin"] = plugin
                    entry["tab"] = tab
                    entry["size"] = f"{width}x{height}"
                    entry["defect"] = "empty-tab"
                    found.append(entry)
                for entry in json.loads(cdp.eval(PAGER_PROBE)):
                    entry["plugin"] = plugin
                    entry["tab"] = tab
                    entry["size"] = f"{width}x{height}"
                    entry["defect"] = "table-without-pager"
                    found.append(entry)
    finally:
        browser_guard.kill_tree(browser)
    return found


def main() -> int:
    plugins = [p.name for p in sorted((ROOT / "games").iterdir())
               if (p / "editor.html").is_file()]
    findings: list[dict] = []
    for plugin in plugins:
        for width, height in ((1600, 950), (1280, 720)):
            findings.extend(sweep(plugin, width, height))
    pagerless = [row for row in findings if row.get("defect") == "table-without-pager"]
    empty = [row for row in findings if row.get("defect") == "empty-tab"]
    clipped = [row for row in findings
               if row.get("defect") not in ("table-without-pager", "empty-tab")]
    # Twenty printed lines hid most of a failure, so every entry is also
    # written out; grouping there is what makes a shared cause obvious.
    report = ROOT / "out" / "no-clipped-text.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(
        {"plugins": plugins, "clipped": clipped, "pagerless": pagerless,
         "empty": empty}, indent=1), encoding="utf-8")
    print(json.dumps({"plugins": plugins, "clipped": len(clipped),
                      "pagerless": len(pagerless), "emptyTabs": len(empty),
                      "report": str(report)}))
    for entry in (clipped + pagerless + empty)[:20]:
        print(json.dumps(entry, ensure_ascii=True))
    if clipped or pagerless or empty:
        raise AssertionError(
            f"{len(clipped)} clipped text boxes, {len(pagerless)} tables without "
            f"a pager, {len(empty)} tabs rendering nothing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
