"""Fail when a plugin screen leaves a band of dead space at the bottom.

A view is allowed to be short. It is not allowed to paint its content into the
top of the window and leave the rest of the region empty, which is what a bare
status line inside a full-height region looks like: one sentence at the top and
several hundred pixels of nothing under it.

The measurement is deliberately crude, because the complaint is crude. For each
tab, find the lowest bottom edge of anything that paints, and compare it with
the bottom of the region the view was given. A gap wider than a fifth of the
window is dead space.

Usage:
    python tools/verify_no_dead_space.py [plugin ...] [--size WxH] [--live]
"""

from __future__ import annotations

import argparse
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

from render_crime_editors_55_62 import Cdp, free_port, wait_eval, wait_json  # noqa: E402
import browser_guard  # noqa: E402
from shot import EDGE, STUB, session_for  # noqa: E402

# The share of the window a view may leave unpainted at the bottom before the
# screen reads as broken rather than merely short.
ALLOWED_GAP = 0.2

# Screens whose slack is a consequence of their content's own fixed shape, not
# of a layout that failed to fill. Blank's Graphs tab draws two curve cards side
# by side; the drawing is locked to 2:1, so at any width where both cards fit
# the row, neither can be tall enough to reach the bottom of the panel. Making
# it fill means one graph per screen and scrolling for the second, which is
# worse. Anything added here needs that kind of reason, in writing.
ACCEPTED = {"blank/graphs"}

# Rows that share a top edge are rows painted on top of one another. This is
# the cheapest possible check for the whole family of grid-track bugs, where a
# table declares fewer tracks than it holds rows and the declared tracks then
# resolve to zero height.
OVERLAP_PROBE = r"""
(() => {
  const bad = [];
  for (const list of document.querySelectorAll('.lex-column-list, .lex-list')) {
    const rows = [...list.children].filter(row => row.classList.contains('lex-list-row'));
    const tops = new Map();
    for (const row of rows) {
      const box = row.getBoundingClientRect();
      if (box.height < 1) continue;
      const key = Math.round(box.top);
      tops.set(key, (tops.get(key) || 0) + 1);
    }
    const worst = [...tops.entries()].filter(([, count]) => count > 1)
      .sort((a, b) => b[1] - a[1])[0];
    if (worst) bad.push({cls: list.className.slice(0, 60), stacked: worst[1]});
    const declared = Number(list.style.getPropertyValue('--lex-page-row-count') || 0);
    if (declared && rows.length > declared)
      bad.push({cls: list.className.slice(0, 60), rows: rows.length, declared});
  }
  return bad;
})()
"""

PROBE = r"""
(() => {
  const main = document.querySelector('#main');
  if (!main) return null;
  const region = main.getBoundingClientRect();
  let lowest = region.top;
  const walk = node => {
    for (const child of node.children) {
      const style = getComputedStyle(child);
      if (style.visibility === 'hidden' || style.display === 'none') continue;
      const box = child.getBoundingClientRect();
      if (box.width < 1 || box.height < 1) continue;
      // A container that only holds its children tells us nothing; a
      // container that paints its own frame does.
      const paints = style.backgroundImage !== 'none'
        || (style.backgroundColor !== 'rgba(0, 0, 0, 0)' && style.backgroundColor !== 'transparent')
        || style.borderBottomWidth !== '0px'
        || (child.children.length === 0 && child.textContent.trim() !== '');
      if (paints) lowest = Math.max(lowest, Math.min(box.bottom, region.bottom));
      walk(child);
    }
  };
  walk(main);
  return {top: Math.round(region.top), bottom: Math.round(region.bottom),
          lowest: Math.round(lowest), height: innerHeight};
})()
"""


def tabs_of(cdp) -> list[str]:
    raw = cdp.eval(
        "JSON.stringify([...document.querySelectorAll("
        "'.lex-shell-header nav button[data-tab]')].map(b=>b.dataset.tab))")
    try:
        return [tab for tab in json.loads(raw) if tab]
    except Exception:
        return []


def check(plugin: str, width: int, height: int, live: bool) -> list[str]:
    failures: list[str] = []
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-gap-", ignore_cleanup_errors=True)
    project = tempfile.TemporaryDirectory(prefix="lexeditor-gap-project-")
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    browser = None
    try:
        with session_for(plugin, None if live else project.name) as session:
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
            # A first visit to a tab that indexes a hundred gigabytes of archives
            # is slow. Waiting is correct; timing out reports nothing.
            cdp.ws.settimeout(420)
            cdp.call("Page.enable")
            cdp.call("Runtime.enable")
            cdp.call("Emulation.setDeviceMetricsOverride", {
                "width": width, "height": height, "deviceScaleFactor": 1, "mobile": False})
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": STUB})
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state==='undefined'||!state.booting", 120)
            time.sleep(1.5)
            found = tabs_of(cdp)
            for tab in found or [""]:
                if tab:
                    cdp.eval(f"navigate({tab!r})")
                    time.sleep(1.8)
                raw = cdp.eval(f"JSON.stringify({PROBE})")
                try:
                    box = json.loads(raw)
                except Exception:
                    box = None
                if not box:
                    continue
                try:
                    stacked = json.loads(cdp.eval(f"JSON.stringify({OVERLAP_PROBE})"))
                except Exception:
                    stacked = []
                for entry in stacked or []:
                    if entry.get("stacked"):
                        failures.append(
                            f"{plugin}/{tab or 'default'}: {entry['stacked']} rows painted on "
                            f"top of each other in {entry['cls']}")
                    else:
                        failures.append(
                            f"{plugin}/{tab or 'default'}: {entry['rows']} rows in a table that "
                            f"declares {entry['declared']} grid tracks ({entry['cls']})")
                gap = box["bottom"] - box["lowest"]
                if gap > box["height"] * ALLOWED_GAP and f"{plugin}/{tab}" not in ACCEPTED:
                    failures.append(
                        f"{plugin}/{tab or 'default'}: {gap}px of dead space under the "
                        f"content ({box['height']}px window)")
    finally:
        browser_guard.kill_tree(browser)
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plugins", nargs="*", default=None)
    parser.add_argument("--size", default="1500x950")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    width, height = (int(part) for part in args.size.lower().split("x"))
    plugins = args.plugins or [path.name for path in sorted((ROOT / "games").iterdir())
                               if (path / "editor.html").exists()]
    failures: list[str] = []
    for plugin in plugins:
        try:
            failures.extend(check(plugin, width, height, args.live))
        except Exception as error:  # a plugin that will not boot is its own report
            failures.append(f"{plugin}: could not be measured ({error})")
    for line in failures:
        print(line)
    print(f"dead-space sweep: {len(failures)} finding(s) over {len(plugins)} plugin(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
