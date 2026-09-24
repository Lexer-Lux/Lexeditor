"""Check initially rendered plugin tabs for hard-clipped text.

This samples each main tab at two window sizes. It does not exercise every
record, subtab, hover state or UI scale. The fast verify_text_clipping gate
separately tests dense shared tables, scaling and the detector itself.
"""

from __future__ import annotations

# Dev caches and outputs live in the temp folder, never in the checkout.
DEV_CACHE = __import__("pathlib").Path(__import__("tempfile").gettempdir()) / "lexeditor-dev"
import sys as _lex_sys
from pathlib import Path as _LexPath
_lex_sys.path.insert(1, str(_LexPath(__file__).resolve().parents[1] / "tools"))
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


def use_installed_games() -> list[str]:
    """Point every plugin at the game the user actually added, when there is one.

    Without this the sweep only ever saw plugins with no data, so every tab
    that needs the installed game rendered an "unavailable" panel and every
    defect in the real tables - a clipped Sell column, a header rectangle, a
    crushed boolean label - went unseen while the sweep reported zero. The
    roots come from Lexeditor's own saved installations, so this checks what
    the user has, and quietly does nothing on a machine with no games added.
    """
    config = (Path(os.environ.get("LOCALAPPDATA", "")) / "Lexeditor"
              / "game-installations.json")
    if not config.is_file():
        return []
    try:
        games = (json.loads(config.read_text(encoding="utf-8")).get("games") or {})
    except (OSError, ValueError):
        return []
    from core import plugin_api  # noqa: F401  (imported for its side-effect-free specs)
    from app import discover_plugins
    plugins = discover_plugins()
    used = []
    for plugin_id, info in games.items():
        plugin = plugins.get(plugin_id)
        root = (info or {}).get("root")
        spec = getattr(plugin, "installation", None)
        if not plugin or not root or spec is None or not Path(root).is_dir():
            continue
        os.environ.setdefault(spec.root_env, str(root))
        used.append(plugin_id)
    return used
from shot import EDGE, STUB, session_for  # noqa: E402
import browser_guard  # noqa: E402

# Share the exact detector with the fast browser regression gate.
PROBE = (ROOT / "tools/text_clipping_probe.js").read_text(encoding="utf-8")


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
    // The pager does not have to live inside the shared paged list-detail: a
    // table composed as its own pane keeps one beside it. What must be true is
    // that a record list has a pager somewhere above it - so walk up, rather
    // than naming one container. (closest() with a longer selector list finds a
    // NEARER ancestor, which is the opposite of being more permissive.)
    let paged=false;
    for(let node=list.parentElement;node&&node!==document.body;node=node.parentElement){
      if(node.querySelector(':scope .lex-pager')){paged=true;break;}
    }
    if(paged) continue;
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


# A column's sort control is a transparent hit area drawn inside the header
# cell's own box. A theme that skins every `button` fills it, and the result is
# a second rectangle painted inside every header cell - which is exactly what
# FF7R shipped. Nothing about that is visible in the plugin's own source, so it
# has to be caught by measuring what the browser actually paints.
CHROME_PROBE = r"""
(()=>{
  const opaque=value=>{
    if(!value||value==='none') return false;
    const m=value.match(/rgba?\(([^)]+)\)/);
    if(!m) return true;
    const parts=m[1].split(',').map(s=>parseFloat(s));
    return parts.length<4 || parts[3]>0.02;
  };
  const bad=[];
  for(const control of document.querySelectorAll(
      '.lex-column-list-head-cell .lex-column-sort, .lex-column-list-head-cell .lex-info-help')){
    const cs=getComputedStyle(control);
    const painted=[];
    if(opaque(cs.backgroundColor)) painted.push('background '+cs.backgroundColor);
    if(parseFloat(cs.borderTopWidth)>0&&cs.borderTopStyle!=='none')
      painted.push('border '+cs.borderTopWidth);
    if(!painted.length) continue;
    // The info bubble is a filled disc by design; only a squared-off fill on it
    // reads as a stray rectangle.
    if(control.classList.contains('lex-info-help')
       && /50%|9999px/.test(cs.borderRadius)) continue;
    bad.push({control:String(control.className).slice(0,30),
              label:(control.textContent||'').trim().slice(0,20),painted});
  }
  return JSON.stringify(bad.slice(0,10));
})()
"""


# A few shared containers are given a fixed share of their parent and clip what
# does not fit. That is invisible to the leaf-text sweep, because the box doing
# the cutting has children rather than text of its own - which is how a detail
# panel spent weeks slicing the source line under every record name in half.
# These are named explicitly; a general ancestor check was tried and drowned in
# false positives.
CONTAINER_PROBE = r"""
(()=>{
  const bad=[];
  const names=['.lex-detail-panel-heading','.lex-detail-section-title',
               '.lex-column-list-header','.lex-pager'];
  for(const node of document.querySelectorAll(names.join(','))){
    const cs=getComputedStyle(node);
    if(cs.display==='none'||cs.visibility==='hidden') continue;
    if(!/(hidden|clip)/.test(cs.overflowX+' '+cs.overflowY)) continue;
    const overW=node.scrollWidth-node.clientWidth;
    const overH=node.scrollHeight-node.clientHeight;
    if(overW>1||overH>1){
      bad.push({cls:String(node.className).slice(0,40),
                text:(node.textContent||'').trim().slice(0,30),overW,overH});
    }
  }
  return JSON.stringify(bad.slice(0,10));
})()
"""


# Two controls that keep silently regressing, checked by measuring what is on
# screen rather than by reading the CSS.
#
# The boolean leader arrow exists to connect a property name to the checkbox it
# governs. When a layout change widened the row, the arrow kept its old cap and
# stopped in mid-air, pointing at nothing - the "can sell arrow bugged" report.
#
# The value slider is only meaningful when a pixel of travel is worth a sensible
# amount. Offered over a raw 32-bit range it writes tens of millions into a
# price on a drag to the middle, which reads as a broken control.
CONTROLS_PROBE = r"""
(()=>{
  const bad=[];
  for(const field of document.querySelectorAll('.lex-boolean-field')){
    const arrow=field.querySelector('.lex-field-boolean-arrow');
    const target=field.querySelector('.lex-detail-field-control input,.lex-detail-field-control select');
    if(!arrow||!target) continue;
    const a=arrow.getBoundingClientRect(), t=target.getBoundingClientRect();
    if(a.width<1||t.width<1) continue;
    const gap=t.left-a.right;
    if(gap>14){
      bad.push({kind:'arrow-short-of-control',gap:Math.round(gap),
                label:(field.querySelector('.lex-detail-field-label')?.textContent||'').trim().slice(0,24)});
    }
  }
  // Ellipsising a number changes its value rather than shortening its label,
  // so a numeric cell is never allowed to truncate. This catches it whether the
  // clip comes from a column width or from a plugin's own stylesheet.
  for(const cell of document.querySelectorAll('.lex-column-list-cell.lex-column-align-end,'
      +'.lex-column-list-cell.lex-numbered-id-cell')){
    const text=cell.querySelector('.lex-column-cell-text');
    if(!text) continue;
    if(text.scrollWidth-text.clientWidth>1){
      bad.push({kind:'numeric-cell-truncated',
                value:(text.textContent||'').trim().slice(0,16),
                lost:Math.round(text.scrollWidth-text.clientWidth)});
    }
  }
  // A record table wider than the panel holding it puts its last column half
  // off the edge. It technically scrolls, but it reads as a cut-off column and
  // it is always a column-width mistake rather than a deliberate choice.
  for(const list of document.querySelectorAll('.lex-column-list')){
    if(!list.querySelector('[aria-selected]')) continue;
    const host=list.closest('.lex-list');
    if(!host) continue;
    const over=list.scrollWidth-host.clientWidth;
    if(over>2){
      bad.push({kind:'table-wider-than-panel',over:Math.round(over),
                label:list.getAttribute('aria-label')||''});
    }
  }
  for(const fill of document.querySelectorAll('.lex-has-value-fill')){
    const input=fill.querySelector('input[type="number"]');
    if(!input) continue;
    const low=Number(input.min), high=Number(input.max);
    const step=Number(input.step)||1;
    if(!Number.isFinite(low)||!Number.isFinite(high)||high<=low) continue;
    const span=(high-low)/step;
    if(span>100000){
      bad.push({kind:'slider-over-unusable-range',span:Math.round(span),
                label:(input.getAttribute('aria-label')||input.name||'').slice(0,24)});
    }
  }
  return JSON.stringify(bad.slice(0,10));
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
            # Reading a real game's tables takes far longer than an empty
            # project did, and the shared harness's one-minute socket timeout
            # killed the whole sweep partway through rather than reporting
            # anything. Give a live game room to answer.
            try:
                cdp.ws.settimeout(420)
            except Exception:  # pragma: no cover - harness detail
                pass
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
              try:
                if tab:
                    cdp.eval(
                        "(()=>{const b=[...document.querySelectorAll('nav button[data-tab]')]"
                        f".find(x=>x.dataset.tab==={json.dumps(tab)});if(b)b.click();}})()")
                    time.sleep(.55)
                wait_eval(cdp, "document.fonts.status==='loaded'", 30)
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
                for entry in json.loads(cdp.eval(CHROME_PROBE)):
                    entry["plugin"] = plugin
                    entry["tab"] = tab
                    entry["size"] = f"{width}x{height}"
                    entry["defect"] = "boxed-header-control"
                    found.append(entry)
                for entry in json.loads(cdp.eval(CONTAINER_PROBE)):
                    entry["plugin"] = plugin
                    entry["tab"] = tab
                    entry["size"] = f"{width}x{height}"
                    entry["defect"] = "clipped-container"
                    found.append(entry)
                for entry in json.loads(cdp.eval(CONTROLS_PROBE)):
                    entry["plugin"] = plugin
                    entry["tab"] = tab
                    entry["size"] = f"{width}x{height}"
                    entry["defect"] = "broken-control"
                    found.append(entry)
                for entry in json.loads(cdp.eval(PAGER_PROBE)):
                    entry["plugin"] = plugin
                    entry["tab"] = tab
                    entry["size"] = f"{width}x{height}"
                    entry["defect"] = "table-without-pager"
                    found.append(entry)
              except Exception as error:  # one tab must not lose the sweep
                found.append({"plugin": plugin, "tab": tab,
                              "size": f"{width}x{height}", "defect": "probe-failed",
                              "reason": f"{type(error).__name__}: {error}"[:160]})
                break
    finally:
        browser_guard.kill_tree(browser)
    return found


def main() -> int:
    live = use_installed_games()
    if live:
        print(json.dumps({"usingInstalledGames": sorted(live)}))
    plugins = [p.name for p in sorted((ROOT / "plugins").iterdir())
               if (p / "editor.html").is_file()]
    findings: list[dict] = []
    for plugin in plugins:
        for width, height in ((1600, 950), (1280, 720)):
            findings.extend(sweep(plugin, width, height))
    pagerless = [row for row in findings if row.get("defect") == "table-without-pager"]
    boxed = [row for row in findings if row.get("defect") == "boxed-header-control"]
    cropped = [row for row in findings if row.get("defect") == "clipped-container"]
    controls = [row for row in findings if row.get("defect") == "broken-control"]
    unprobed = [row for row in findings if row.get("defect") == "probe-failed"]
    empty = [row for row in findings if row.get("defect") == "empty-tab"]
    clipped = [row for row in findings
               if row.get("defect") not in ("table-without-pager", "empty-tab",
                                            "boxed-header-control",
                                            "clipped-container", "broken-control",
                                            "probe-failed")]
    # Twenty printed lines hid most of a failure, so every entry is also
    # written out; grouping there is what makes a shared cause obvious.
    report = DEV_CACHE / "no-clipped-text.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(
        {"plugins": plugins, "clipped": clipped, "pagerless": pagerless,
         "empty": empty, "boxed": boxed, "cropped": cropped, "controls": controls,
         "unprobed": unprobed}, indent=1), encoding="utf-8")
    print(json.dumps({"plugins": plugins, "clipped": len(clipped),
                      "pagerless": len(pagerless), "emptyTabs": len(empty),
                      "boxedHeaderControls": len(boxed),
                      "clippedContainers": len(cropped),
                      "brokenControls": len(controls),
                      "tabsNotProbed": len(unprobed),
                      "report": str(report)}))
    for entry in (clipped + pagerless + empty + boxed + cropped + controls + unprobed)[:20]:
        print(json.dumps(entry, ensure_ascii=True))
    if clipped or pagerless or empty or boxed or cropped or controls or unprobed:
        raise AssertionError(
            f"{len(clipped)} clipped text boxes, {len(pagerless)} tables without "
            f"a pager, {len(empty)} tabs rendering nothing, {len(boxed)} header "
            f"controls painting their own box, {len(cropped)} shared "
            f"containers cutting off what they hold, {len(controls)} controls "
            f"pointing nowhere or spanning an unusable range, {len(unprobed)} "
            f"tabs that could not be measured")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
