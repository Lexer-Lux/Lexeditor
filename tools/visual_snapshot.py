"""Screenshot every tab of every plugin, opened the way the app opens them.

    python tools/visual_snapshot.py <output-folder> [plugin ...]

Run it from a checkout (the current one, or an older worktree) to capture how
that version looks with the installed games and the current mod projects. Two
runs side by side are a visual diff: what a change did to the screen, which no
DOM assertion can say.

Each plugin is opened through the desktop host's own open_plugin, so the page
gets the same game paths, project and fonts it gets in the app. Nothing is
saved; the page is only looked at.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright  # noqa: E402

from app import discover_plugins  # noqa: E402
from desktop_host import HostApi  # noqa: E402

SIZE = {"width": 1600, "height": 900}


def settle(page, ms=700):
    page.wait_for_timeout(ms)


def shoot_plugin(browser, api, plugin_id: str, out: Path) -> list[str]:
    notes = []
    try:
        opened = api.open_plugin(plugin_id)
    except Exception as error:  # noqa: BLE001 - a plugin that cannot open is a result
        return [f"{plugin_id}: cannot open ({error})".replace("\n", " ")[:300]]
    page = browser.new_page(viewport=SIZE)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.route("**/api/**", lambda route: route.abort()
                   if route.request.method not in ("GET", "HEAD") else route.continue_())
        page.goto(opened["url"].split("?")[0], wait_until="domcontentloaded", timeout=60000)
        deadline = time.time() + 90
        while time.time() < deadline:
            if page.locator("nav button[data-tab]").count() and not page.evaluate(
                    "document.documentElement.classList.contains('lex-transition-loading')"):
                break
            page.wait_for_timeout(500)
        settle(page, 2500)
        tabs = page.evaluate("[...document.querySelectorAll('nav button[data-tab]')]"
                             ".map(b=>b.dataset.tab).filter(t=>t&&t!=='settings')")
        for tab in tabs or [None]:
            if tab:
                try:
                    page.locator(f'nav button[data-tab="{tab}"]').first.click(timeout=5000)
                except Exception:  # noqa: BLE001
                    notes.append(f"{plugin_id}/{tab}: tab not clickable")
                    continue
                settle(page, 1800)
            # Select a record by its first cell's corner, never by the middle of
            # a row, where an editable cell's input would take the click.
            row = page.locator("#main .lex-list-row")
            if row.count():
                try:
                    row.first.click(position={"x": 4, "y": 4}, timeout=3000)
                    settle(page, 900)
                except Exception:  # noqa: BLE001
                    pass
            page.mouse.move(2, SIZE["height"] - 2)
            settle(page, 200)
            page.screenshot(path=str(out / f"{plugin_id}-{tab or 'page'}.png"))
        # Page-level subtabs are part of the look too: shoot each on the last tab
        # only when a plugin has them on its first screen.
    except Exception as error:  # noqa: BLE001
        notes.append(f"{plugin_id}: {error}".replace("\n", " ")[:300])
    finally:
        if errors:
            notes.append(f"{plugin_id}: page errors: " + " | ".join(errors[:3])[:300])
        page.close()
    return notes


def main() -> int:
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    plugins = discover_plugins()
    wanted = sys.argv[2:] or [pid for pid in sorted(plugins) if pid != "ff7_2013"]
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
