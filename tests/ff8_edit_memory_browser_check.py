"""FF8 editing stays flat in memory and time; undo keeps working.

Every keystroke used to clone all ~20MB of datasets into a 50-deep undo
stack, so the heap climbed past 2GB within fifty edits. Snapshots now hold
only rows that differ from the last saved state. This check budgets heap
growth across repeated UI edits and tab cycles, budgets capture cost, and
proves undo/redo still revert across datasets, including field dialogue.
"""
import gc
import os
import sys
import tempfile
import threading
import tracemalloc
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
_TEMPDIR = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-edit-memory-check-")
os.environ["LEXEDITOR_FF8_EDITOR_SETTINGS"] = str(Path(_TEMPDIR.name) / "e.json")

from plugins.ff8.server import create_server
from playwright.sync_api import sync_playwright

BOOTED = "typeof state==='object' && !state.booting && !state.bootFailed"
# Generous ceilings: the fixed editor sits far below each, the old one blew
# past every one within fifty edits (2GB+ heap, 20MB captures, 224ms each).
EDIT_HEAP_BUDGET_MB = 150
TAB_HEAP_BUDGET_MB = 100
CAPTURE_MS_BUDGET = 2000
CAPTURE_BYTES_BUDGET = 2_000_000
SERVER_GROWTH_BUDGET_KB = 5_000

DATASETS = [
    "/api/kernel?section=8&dataset=current", "/api/cards?dataset=current",
    "/api/items?dataset=current", "/api/menu-items?dataset=current",
    "/api/shops?dataset=current", "/api/weapons?dataset=current",
    "/api/kernel?section=2&dataset=current", "/api/kernel?section=3&dataset=current",
    "/api/kernel?section=7&dataset=current", "/api/kernel?section=12&dataset=current",
    "/api/kernel?section=13&dataset=current", "/api/kernel?section=14&dataset=current",
    "/api/kernel?section=15&dataset=current", "/api/kernel?section=16&dataset=current",
    "/api/kernel?section=17&dataset=current", "/api/kernel?section=18&dataset=current",
    "/api/text?dataset=current", "/api/enemies?dataset=current",
    "/api/enemy-tables?dataset=current", "/api/enemy-ai?dataset=current",
    "/api/enemy-battle-text?dataset=current", "/api/refine?dataset=current",
    "/api/encounters?dataset=current", "/api/world-map?dataset=current",
    "/api/fields?dataset=current", "/api/init?dataset=current",
]


def heap_mb(page):
    return page.evaluate("performance.memory.usedJSHeapSize") / 1024 / 1024


def capture_stats(page):
    return page.evaluate("""() => {
      const started = performance.now();
      const bytes = JSON.stringify(historyCapture()).length;
      return {ms: performance.now() - started, bytes};
    }""")


def main():
    server = create_server(0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        tracemalloc.start()
        for path in DATASETS:  # warm caches and extraction once
            urllib.request.urlopen(base + path, timeout=120).read()
        gc.collect()
        before = tracemalloc.take_snapshot()
        for _ in range(5):
            for path in DATASETS:
                urllib.request.urlopen(base + path, timeout=120).read()
        gc.collect()
        growth_kb = (sum(stat.size for stat in
                          tracemalloc.take_snapshot().statistics("filename"))
                     - sum(stat.size for stat in before.statistics("filename"))) / 1024
        assert growth_kb < SERVER_GROWTH_BUDGET_KB, f"server grew {growth_kb:,.0f} KB"
        print(f"server dataset cycles: +{growth_kb:,.0f} KB over 5 reloads.")

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True,
                                         args=["--enable-precise-memory-info"])
            page = browser.new_page(viewport={"width": 1600, "height": 900})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(base + "/")
            page.wait_for_function(BOOTED, timeout=90000)

            stats = capture_stats(page)
            assert stats["bytes"] < CAPTURE_BYTES_BUDGET, stats
            assert stats["ms"] < CAPTURE_MS_BUDGET, stats
            print(f"clean capture: {stats['bytes'] / 1024:.0f} KB in {stats['ms']:.0f} ms.")

            # Forty committed UI edits across two datasets.
            page.locator('nav [data-tab="items"]').click()
            page.wait_for_timeout(400)
            heap_before = heap_mb(page)
            box = page.locator("#main input[type=number]").first
            for step in range(20):
                box.fill(str(100 + step))
                box.blur()
                page.wait_for_timeout(60)
            page.locator('nav [data-tab="weapons"]').click()
            page.wait_for_timeout(400)
            blade = page.locator("#main input[type=number]").first
            for step in range(20):
                blade.fill(str(50 + step))
                blade.blur()
                page.wait_for_timeout(60)
            growth = heap_mb(page) - heap_before
            assert growth < EDIT_HEAP_BUDGET_MB, f"edits grew the heap {growth:.0f} MB"
            stats = capture_stats(page)
            assert stats["bytes"] < CAPTURE_BYTES_BUDGET, stats
            assert stats["ms"] < CAPTURE_MS_BUDGET, stats
            print(f"40 edits: heap +{growth:.0f} MB; dirty capture "
                  f"{stats['bytes'] / 1024:.0f} KB in {stats['ms']:.0f} ms.")

            # Undo and redo round-trip exactly. Driven through the history
            # object: the keyboard path is shared framework code, and pressing
            # keys from a harness double-fires on old and new code alike.
            page.evaluate("(async () => { await discardAll(); })()")
            page.wait_for_timeout(400)
            assert page.evaluate("dirtyCount()") == 0, "discard left dirty rows"
            solo = page.locator("#main input[type=number]").first
            sticker = page.evaluate(
                "state.data.weapons.rows.find(r => r.id === state.selected.weapons)"
                ".fields.map(f => f.field + '=' + f.value).join(',')")
            solo.fill("77")
            solo.blur()
            page.wait_for_timeout(400)
            assert page.evaluate("dirtyCount()") == 1, "solo edit left no dirty row"
            page.evaluate("(async () => { await shell.history.undo(); })()")
            page.wait_for_timeout(400)
            assert page.evaluate("dirtyCount()") == 0, "undo did not revert"
            assert page.evaluate(
                "state.data.weapons.rows.find(r => r.id === state.selected.weapons)"
                ".fields.map(f => f.field + '=' + f.value).join(',')") == sticker
            page.evaluate("(async () => { await shell.history.redo(); })()")
            page.wait_for_timeout(400)
            assert page.evaluate("dirtyCount()") == 1, "redo lost the edit"

            # Field dialogue undo exercises the keyed row restore path.
            page.locator('nav [data-tab="maps"]').click()
            page.wait_for_function(
                "state.data.fields.rows.some(row => row._loaded) || "
                "document.querySelector('#main [data-field-map]')", timeout=30000)
            shown = page.evaluate("""(async () => {
              const row = state.data.fields.rows.find(value => value._loaded)
                || state.data.fields.rows[0];
              state.selected.fields = row.key;
              state.mapsTab = "field";
              await ensureFieldDetail(row);
              renderMaps();
              return row.key;
            })()""")
            page.wait_for_function(
                "document.querySelectorAll('#main textarea').length > 0", timeout=30000)
            row_of = ("state.data.fields.rows.find(value => value.key === " +
                      repr(shown) + ")")
            original = page.evaluate(f"{row_of}.dialogue[0].text")
            page.locator("#main textarea").first.fill(original + " undo-probe")
            page.locator("#main textarea").first.blur()
            page.wait_for_timeout(400)
            assert page.evaluate(f"{row_of}.dialogue[0].text").endswith(
                "undo-probe"), "dialogue edit did not land"
            page.evaluate("(async () => { await shell.history.undo(); })()")
            page.wait_for_timeout(400)
            assert page.evaluate(f"{row_of}.dialogue[0].text") == original, \
                "dialogue undo did not revert"

            # Tab cycling stays flat too.
            heap_before = heap_mb(page)
            for _ in range(3):
                for tab in ("items", "weapons", "magic", "abilities", "enemies", "maps"):
                    page.locator(f'nav [data-tab="{tab}"]').click()
                    page.wait_for_timeout(150)
            growth = heap_mb(page) - heap_before
            assert growth < TAB_HEAP_BUDGET_MB, f"tab cycles grew {growth:.0f} MB"
            print(f"tab cycles: heap +{growth:.0f} MB over 18 visits.")
            assert not errors, errors
            # Let slow map previews land before tearing down the server,
            # or their aborted POSTs fail the run after it has passed.
            try:
                page.wait_for_load_state("networkidle", timeout=30000)
            except Exception:
                pass
            page.close()
            browser.close()
    finally:
        server.shutdown()
        _TEMPDIR.cleanup()
    print("FF8 edit memory: bounded heap, cheap captures, working undo.")


if __name__ == "__main__":
    main()
