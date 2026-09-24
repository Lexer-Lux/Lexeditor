"""Screenshot every tab of every plugin, opened the way the app opens them.

    .venv/Scripts/python.exe tools/visual_snapshot.py <output-folder> [--styles] [plugin ...]

Use the project's Python runtime. Native plugin decoders can require its
Python ABI; an unrelated system Python can open pages but fail to load models.

Run it from a checkout (the current one, or an older worktree) to capture how
that version looks with the installed games and the current mod projects. Two
runs side by side are a visual diff: what a change did to the screen, which no
DOM assertion can say.

Each plugin is opened through the desktop host's own open_plugin, so the page
gets the same game paths, project and fonts it gets in the app. Nothing is
saved; the page is only looked at.

With --styles, each view also records the computed style and box of every
visible element (<plugin>-<tab>.styles.json). tools/style_compare.py lists
what differs between two runs, which is how a CSS refactor proves it changed
nothing it did not mean to.
"""
from __future__ import annotations

import json

import sys
import time
from urllib.parse import urlsplit
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright  # noqa: E402

from app import discover_plugins  # noqa: E402
from core.desktop_host import HostApi  # noqa: E402

SIZE = {"width": 1600, "height": 900}
STYLES = False
# The smallest text a reader is expected to read, in CSS pixels.
MIN_TEXT_PX = 9
TEXT_AUDIT = (Path(__file__).resolve().parent / "text_audit.js").read_text(encoding="utf-8")
TEXT_AUDIT = TEXT_AUDIT[TEXT_AUDIT.index("(minimum) =>"):]
TABS_FILTER = set()

# The properties that decide how an element looks and where it sits.
PROPERTIES = """
display position top right bottom left float z-index box-sizing
margin-top margin-right margin-bottom margin-left
padding-top padding-right padding-bottom padding-left
border-top-width border-right-width border-bottom-width border-left-width
border-top-style border-right-style border-bottom-style border-left-style
border-top-color border-right-color border-bottom-color border-left-color
border-top-left-radius border-top-right-radius border-bottom-left-radius border-bottom-right-radius
outline-style outline-width outline-color box-shadow
background-color background-image background-position background-size
color opacity visibility filter mix-blend-mode
font-family font-size font-weight font-style line-height letter-spacing word-spacing
text-transform text-align text-decoration-line text-shadow text-overflow white-space
overflow-wrap word-break vertical-align
overflow-x overflow-y
flex-direction flex-wrap flex-grow flex-shrink flex-basis order
align-items align-self align-content justify-content justify-items justify-self
grid-template-columns grid-template-rows grid-column-start grid-column-end
grid-row-start grid-row-end grid-auto-flow column-gap row-gap
min-width max-width min-height max-height
transform cursor pointer-events user-select
""".split()

CAPTURE = """props => {
  const out = {};
  const walk = (node, path) => {
    const style = getComputedStyle(node);
    if (style.display === 'none') return;
    const box = node.getBoundingClientRect();
    const entry = {box: [box.x, box.y, box.width, box.height].map(v => Math.round(v * 2) / 2)};
    for (const name of props) entry[name] = style.getPropertyValue(name);
    out[path] = entry;
    const counts = {};
    for (const child of node.children) {
      if (child.matches('script,style,link,template,svg *')) continue;
      const key = child.tagName.toLowerCase() + ([...child.classList].filter(c => !/^(active|selected|sel|hover|focus|lex-value-modified)$/.test(c)).sort().map(c => '.' + c).join(''));
      counts[key] = (counts[key] || 0) + 1;
      walk(child, path + ' > ' + key + (counts[key] > 1 ? ':' + counts[key] : ''));
    }
  };
  walk(document.body, 'body');
  return out;
}"""


def settle(page, ms=700):
    page.wait_for_timeout(ms)
    page.wait_for_function(r"""() => {
      if (document.documentElement.classList.contains('lex-transition-loading')) return false;
      const main = document.querySelector('#main');
      if (!main || !main.children.length) return false;
      return ![...main.querySelectorAll('.loading,.lex-notice')].some(node =>
        node.offsetParent !== null && /^loading\b/i.test(node.textContent.trim()));
    }""", timeout=90000)


SUBTABS = ":is(#main,#toolbar) .lex-subtab-bar:not([hidden]) > .lex-subtab-button"

# Views a plugin keeps off its tab bar, opened by name with its navigate().
# Blank's demonstration pages are the live samples for the heavier components.
EXTRA_VIEWS = {"blank": ["one", "two", "three", "subtabs", "tweaks", "graphs"],
               "warband": ["dashboard", "datamap", "manuals"],
               "rdr": ["project", "datamap"]}


def visible_subtab_count(page, depth: int) -> int:
    """How many subtab buttons the depth-th visible subtab bar holds."""
    return page.evaluate("""([selector, depth]) => {
      const bars = [...document.querySelectorAll(':is(#main,#toolbar) .lex-subtab-bar:not([hidden])')]
        .filter(bar => bar.offsetParent !== null);
      return bars[depth] ? bars[depth].querySelectorAll(':scope > .lex-subtab-button').length : 0;
    }""", [SUBTABS, depth])


def click_subtab(page, depth: int, index: int) -> bool:
    return page.evaluate("""([depth, index]) => {
      const bars = [...document.querySelectorAll(':is(#main,#toolbar) .lex-subtab-bar:not([hidden])')]
        .filter(bar => bar.offsetParent !== null);
      const button = bars[depth]?.querySelectorAll(':scope > .lex-subtab-button')[index];
      if (!button) return false;
      button.click();
      return true;
    }""", [depth, index])


def subtab_paths(page) -> list[tuple[int, ...]]:
    """(i,) for each subtab of the first bar, and (i, j) for each subtab of a
    second bar that subtab i shows. Tabs already open count once."""
    paths = []
    for first in range(visible_subtab_count(page, 0)):
        paths.append((first,))
        if not open_subtabs(page, (first,)):
            continue
        for second in range(visible_subtab_count(page, 1)):
            paths.append((first, second))
    return paths


def open_subtabs(page, path) -> bool:
    for depth, index in enumerate(path):
        if not click_subtab(page, depth, index):
            return False
        settle(page, 900)
    return True


def select_first_row(page) -> None:
    # Select a record by its first cell's corner, never by the middle of a
    # row, where an editable cell's input would take the click.
    row = page.locator("#main .lex-list-row")
    if row.count():
        try:
            row.first.click(position={"x": 4, "y": 4}, timeout=3000)
            settle(page, 900)
        except Exception:  # noqa: BLE001
            pass


def capture(page, out: Path, name: str) -> None:
    page.mouse.move(2, SIZE["height"] - 2)
    settle(page, 200)
    page.screenshot(path=str(out / f"{name}.png"))
    # Every view is also read for text a person cannot read: cut off by a box
    # that does not scroll, or drawn too small. tools/text_audit_report.py
    # lists them; a view with none writes an empty list.
    issues = page.evaluate(TEXT_AUDIT, MIN_TEXT_PX)
    (out / f"{name}.text.json").write_text(json.dumps(issues, indent=1), encoding="utf-8")
    if STYLES:
        styles = page.evaluate(CAPTURE, PROPERTIES)
        (out / f"{name}.styles.json").write_text(
            json.dumps(styles, indent=0, sort_keys=True), encoding="utf-8")


def shoot_plugin(browser, api, plugin_id: str, out: Path) -> list[str]:
    notes = []
    # A game is refused while the host is still checking its files; that check
    # starts with the host, so wait for it rather than report it.
    deadline = time.time() + 600
    while True:
        try:
            opened = api.open_plugin(plugin_id)
            break
        except Exception as error:  # noqa: BLE001 - a plugin that cannot open is a result
            if "check" in str(error).lower() and time.time() < deadline:
                time.sleep(2)
                continue
            return [f"{plugin_id}: cannot open ({error})".replace("\n", " ")[:300]]
    page = browser.new_page(viewport=SIZE)
    errors = []
    page.on("pageerror", lambda error: errors.append(getattr(error, "stack", None) or str(error)))
    try:
        # This POST renders a supplied preview in memory; it does not save it.
        def read_only_route(route):
            # RDR configures its helper during boot. The UI only needs the
            # following dashboard read; snapshots must not change that helper.
            if (plugin_id == "rdr" and route.request.method == "POST"
                    and urlsplit(route.request.url).path == "/api/redhook/configure"):
                route.fulfill(json={"configured": False, "snapshot": True})
                return
            preview = (plugin_id == "ff8" and route.request.method == "POST"
                       and urlsplit(route.request.url).path == "/api/field/background-preview")
            if route.request.method in ("GET", "HEAD") or preview:
                route.continue_()
            else:
                route.abort()
        page.route("**/api/**", read_only_route)
        page.goto(opened["url"].split("?")[0], wait_until="domcontentloaded", timeout=60000)
        deadline = time.time() + 90
        while time.time() < deadline:
            if page.locator("nav button[data-tab]").count() and not page.evaluate(
                    "document.documentElement.classList.contains('lex-transition-loading')"):
                break
            page.wait_for_timeout(500)
        settle(page, 2500)
        tabs = page.evaluate("[...document.querySelectorAll('nav button[data-tab]')]"
                             ".map(b=>b.dataset.tab).filter(Boolean)")
        if TABS_FILTER:
            tabs = [tab for tab in tabs if tab in TABS_FILTER]
        for tab in tabs or [None]:
            if tab:
                try:
                    page.locator(f'nav button[data-tab="{tab}"]').first.click(timeout=5000)
                except Exception:  # noqa: BLE001
                    notes.append(f"{plugin_id}/{tab}: tab not clickable")
                    continue
                settle(page, 1800)
            select_first_row(page)
            capture(page, out, f"{plugin_id}-{tab or 'page'}")
            # Every subtab on this tab, by position, so a bar that redraws
            # itself after a click is read afresh each time. Subtabs that open
            # further subtabs are followed one level down.
            for path in subtab_paths(page):
                if not open_subtabs(page, path):
                    notes.append(f"{plugin_id}/{tab}/{'-'.join(map(str, path))}: subtab not clickable")
                    continue
                select_first_row(page)
                capture(page, out, f"{plugin_id}-{tab or 'page'}-sub{'-'.join(map(str, path))}")
            if tab:
                # Leave the tab as it was found for the next one.
                page.locator(f'nav button[data-tab="{tab}"]').first.click(timeout=5000)
                settle(page, 400)
        for view in ([] if TABS_FILTER else EXTRA_VIEWS.get(plugin_id, [])):
            page.evaluate(f"navigate('{view}')")
            settle(page, 1200)
            select_first_row(page)
            capture(page, out, f"{plugin_id}-view-{view}")
            for path in subtab_paths(page):
                if open_subtabs(page, path):
                    capture(page, out, f"{plugin_id}-view-{view}-sub{'-'.join(map(str, path))}")
    except Exception as error:  # noqa: BLE001
        notes.append(f"{plugin_id}: {error}".replace("\n", " ")[:300])
        if not page.is_closed():
            # A sick page can stall text reads past the default timeout,
            # which used to raise out of this handler and lose the original
            # error with it. Bound the read so the notes always survive.
            try:
                notes.append(f"{plugin_id}: visible status: " + page.locator('body').inner_text(timeout=15000)[-1600:])
            except Exception:  # noqa: BLE001 - the page can be too sick to read
                notes.append(f"{plugin_id}: body text unreadable within 15s (page unresponsive)")
            try:
                page.screenshot(path=str(out / f"{plugin_id}-failure.png"))
            except Exception:  # noqa: BLE001
                notes.append(f"{plugin_id}: failure screenshot failed")
    finally:
        if errors:
            notes.append(f"{plugin_id}: page errors: " + " | ".join(errors[:3])[:6000])
        page.close()
    return notes


def main() -> int:
    global STYLES, TABS_FILTER
    args = sys.argv[1:]
    for arg in list(args):
        if arg.startswith('--tabs='):
            TABS_FILTER = set(arg.split('=', 1)[1].split(','))
            args.remove(arg)
    if "--styles" in args:
        STYLES = True
        args.remove("--styles")
    out = Path(args[0]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    plugins = discover_plugins()
    wanted = args[1:] or [pid for pid in sorted(plugins) if pid != "ff7_2013"]
    api = HostApi(plugins)
    notes = []
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            for plugin_id in wanted:
                print("shooting", plugin_id, flush=True)
                notes += shoot_plugin(browser, api, plugin_id, out)
        finally:
            browser.close()
            api.stop()
    (out / "notes.txt").write_text("\n".join(notes) + "\n", encoding="utf-8")
    print("\n".join(notes) or "no notes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
