"""FF8 asset tabs: mod-contents-only filtering, previews, saves, and layout.

Serves the real plugin with a scratch project shaped like a character
texture replacer plus SFX replacements, then drives the real UI: the MOD
CONTENTS ONLY checkbox must leave exactly the replaced assets on each of
the SFX, Models, and Textures tabs.
"""
import base64
import json
import os
import shutil
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

TMP = Path(tempfile.mkdtemp(prefix="ff8-asset-tabs-"))
PROJECT = TMP / "project"
MODS = TMP / "mods"
os.environ["LEXEDITOR_FF8_PROJECT"] = str(PROJECT)
os.environ["LEXEDITOR_FF8_MODS_ROOT"] = str(MODS)

from plugins.ff8 import paths  # noqa: E402
from plugins.ff8.server import Handler  # noqa: E402

TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")


def write_fixtures():
    (PROJECT / "direct" / "battle").mkdir(parents=True)
    (PROJECT / "sfx").mkdir(parents=True)
    (PROJECT / "textures" / "battle").mkdir(parents=True)
    (PROJECT / "textures" / "cardgame").mkdir(parents=True)
    MODS.mkdir(parents=True)
    (PROJECT / "mod.json").write_text(json.dumps({"id": "project", "name": "Scratch"}))
    baseline = paths.BASELINE_ROOT / "battle"
    # Replace one monster model with another monster's valid bytes.
    shutil.copy2(baseline / "c0m002.dat", PROJECT / "direct" / "battle" / "c0m001.dat")
    (PROJECT / "sfx" / "5.ogg").write_bytes(b"OggS" + bytes(100))
    (PROJECT / "sfx" / "battle_9.ogg").write_bytes(b"OggS" + bytes(100))
    (PROJECT / "textures" / "battle" / "c0m001.dat_0.png").write_bytes(TINY_PNG)
    (PROJECT / "textures" / "cardgame" / "custom.png").write_bytes(TINY_PNG)
    # A second, managed mod replacing one asset per tab.
    other = MODS / "scratch-asset-mod"
    (other / "sfx").mkdir(parents=True)
    (other / "direct" / "battle").mkdir(parents=True)
    (other / "textures" / "world" / "dat" / "texl").mkdir(parents=True)
    (other / "mod.json").write_text(json.dumps({"id": "scratch-assets", "name": "Scratch Assets"}))
    (other / "sfx" / "11.ogg").write_bytes(b"OggS" + bytes(100))
    # Identical bytes: the Models row still counts as replaced (it carries
    # an override), while the Textures list stays isolated to the texl claim.
    shutil.copy2(baseline / "c0m003.dat", other / "direct" / "battle" / "c0m003.dat")
    (other / "textures" / "world" / "dat" / "texl" / "texture5_0.png").write_bytes(TINY_PNG)


def master_rows(page):
    return page.evaluate("""() => [...document.querySelectorAll(
      '#main .ff8-record-list [role="row"]')].slice(1).map(
      row => (row.textContent || '').replace(/\\s+/g, ' ').trim())""")


def set_mod_only(page, value):
    box = page.get_by_label("Mod contents only")
    (box.check() if value else box.uncheck())
    page.wait_for_timeout(400)


def main():
    write_fixtures()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    from playwright.sync_api import sync_playwright
    errors = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1500, "height": 950})
            page.on("console", lambda message: errors.append(message.text)
                    if message.type == "error" else None)
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{port}/")
            page.wait_for_selector('nav button[data-tab="sfx"]', timeout=90000)
            page.wait_for_function(
                "() => { try { return !state.booting; } catch (e) { return false; } }",
                timeout=180000)
            assert page.evaluate("state.bootFailed") in (None, False), "plugin boot failed"
            assert page.evaluate("state.activeSource") == "mine"
            assert page.evaluate("state.data.sfx.rows.length") == 2791
            assert page.evaluate("state.data.models.rows.length") == 853
            assert page.evaluate("state.data.textures.rows.length") == 502

            page.click('nav button[data-tab="sfx"]')
            set_mod_only(page, True)
            rows = master_rows(page)
            assert len(rows) == 2, f"SFX mod-only rows: {rows}"
            assert any("Sound 5" in row for row in rows), rows
            assert any("Sound 9" in row for row in rows), rows
            page.evaluate("state.selected.sfx = 5")
            page.evaluate("navigate('sfx')")
            page.wait_for_timeout(300)
            assert page.locator("#main audio").count() == 1
            set_mod_only(page, False)

            page.click('nav button[data-tab="models"]')
            set_mod_only(page, True)
            rows = master_rows(page)
            assert len(rows) == 1, f"Models mod-only rows: {rows}"
            assert "c0m001.dat" in rows[0], rows
            assert page.locator("#main .ff8-model-sections").count() == 1
            set_mod_only(page, False)

            page.click('nav button[data-tab="textures"]')
            set_mod_only(page, True)
            rows = master_rows(page)
            assert len(rows) == 3, f"Textures mod-only rows: {rows}"
            assert sum("c0m001" in row for row in rows) == 2, rows
            assert any("custom.png" in row for row in rows), rows
            assert page.locator("#main .lex-detail-panel img").count() >= 1
            set_mod_only(page, False)
            # The file a texture belongs to is the panel subtitle, and it is
            # the way into the tab that edits it: no EDIT section, no button.
            model = page.evaluate("""() => {
              const row = state.data.textures.rows.find(
                r => r.editor === 'models' && r.modelFile);
              state.selected.textures = row.id;
              render();
              return row.modelFile;
            }""")
            page.wait_for_timeout(400)
            assert page.locator("#main .lex-detail-panel-icon img").count() >= 1
            titles = page.evaluate(
                "() => [...document.querySelectorAll("
                "'#main .lex-detail-panel [data-section-title]')].map("
                "node => node.getAttribute('data-section-title'))")
            assert not any(title == "EDIT" for title in titles), titles
            assert page.locator(
                "#main .lex-detail-panel button:has-text('in Models')").count() == 0
            subtitle = page.locator("#main .lex-detail-panel-meta .lex-hoverable")
            assert subtitle.count() >= 1
            assert (subtitle.first.text_content() or "").strip() == model, subtitle.all_text_contents()
            # The framework moves a native title into its own hover card, so
            # the accessible name is what still names the destination.
            assert subtitle.first.get_attribute("aria-label") == f"Open {model} in Models"
            # A hoverable follows its link on a keyboard activation whatever
            # the Alt-click preference is, so the check uses the keyboard.
            subtitle.first.focus()
            subtitle.first.press("Enter")
            page.wait_for_timeout(400)
            assert page.evaluate("state.tab") == "models"
            page.click('nav button[data-tab="textures"]')
            page.wait_for_timeout(300)

            page.evaluate("() => switchProjectSource('mod:scratch-assets')")
            assert page.evaluate("state.activeSource") == "mod:scratch-assets"
            for tab, expected in (("sfx", ["Sound 11"]),
                                  ("models", ["c0m003.dat"]),
                                  ("textures", ["World Texture 6"])):
                page.click(f'nav button[data-tab="{tab}"]')
                assert page.get_by_label("Mod contents only").is_enabled(), tab
                set_mod_only(page, True)
                rows = master_rows(page)
                assert len(rows) == 1, f"{tab} mod-only rows: {rows}"
                assert expected[0] in rows[0], rows
                set_mod_only(page, False)
            page.evaluate("() => switchProjectSource('mine')")
            assert page.evaluate("state.activeSource") == "mine"

            for tab in ("sfx", "models", "textures"):
                page.click(f'nav button[data-tab="{tab}"]')
                page_count = page.evaluate(
                    f"Math.ceil(filtered('{tab}', ['name']).length / state.pageSizes.{tab})")
                for target in sorted({0, page_count // 2, page_count - 1}):
                    page.evaluate(f"state.pages.{tab} = {target}; render()")
                    page.wait_for_timeout(300)
                    overflow = page.evaluate("""() => {
                      const list = document.querySelector('#main .ff8-record-list');
                      return list.scrollWidth - list.clientWidth;
                    }""")
                    assert overflow <= 2, f"{tab} page {target} overflows by {overflow}px"

            page.set_viewport_size({"width": 1024, "height": 800})
            page.wait_for_timeout(300)
            tops = page.evaluate("""() => [...document.querySelectorAll(
              'nav button[data-tab]')].map(node => node.offsetTop)""")
            assert len(set(tops)) == 1, f"tab bar wraps at 1024px: {tops}"
            for tab in ("sfx", "models", "textures"):
                page.click(f'nav button[data-tab="{tab}"]')
                page.wait_for_timeout(300)
                assert page.locator("#main .ff8-record-list").count() == 1

            page.set_viewport_size({"width": 1500, "height": 950})
            page.evaluate("""async () => {
              const row = state.data.sfx.rows.find(r => r.id === 7);
              row.audioBase64 = btoa('OggS' + '\\0'.repeat(100));
              row.audioExt = 'ogg';
              await saveAll();
            }""")
            page.wait_for_timeout(1000)
            assert (PROJECT / "sfx" / "7.ogg").is_file(), "staged SFX was not saved"
            assert page.evaluate(
                "state.data.sfx.rows.find(r => r.id === 7).modFiles.length") == 1
            page.evaluate("""async () => {
              const row = state.data.sfx.rows.find(r => r.id === 7);
              row.audioBase64 = '';
              row.audioRevert = true;
              await saveAll();
            }""")
            page.wait_for_timeout(1000)
            assert not (PROJECT / "sfx" / "7.ogg").exists(), "SFX revert did not delete"

            assert not errors, f"console errors: {errors[:5]}"
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=10)
        shutil.rmtree(TMP, ignore_errors=True)
    print("ff8 asset tabs browser check passed")


if __name__ == "__main__":
    main()
