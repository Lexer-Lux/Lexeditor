"""Asset detail headers carry the shared file-location button.

Seeds a scratch project with one sfx, one texture and one model override,
then proves each asset tab's detail header shows the shared folder button:
enabled with the mod title on replaced rows, disabled with "No file to
reveal" on vanilla rows, and no MOD FILES section anywhere in the details.
"""
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from playwright.sync_api import sync_playwright
from plugins.ff8 import paths
from plugins.ff8.plugin import FF8Session


def seed(project):
    root = Path(project)
    (root / "sfx").mkdir()
    (root / "sfx" / "12.ogg").write_bytes(b"OggS" + bytes(100))
    tex = root / "textures" / "world" / "dat" / "texl"
    tex.mkdir(parents=True)
    (tex / "texture0.png").write_bytes(bytes(100))
    battle = root / "direct" / "battle"
    battle.mkdir(parents=True)
    # A real battle file: enemy stats and AI parse out of the model, so
    # zero bytes here 400 the enemy endpoints and the tab never renders.
    shutil.copy(paths.BASELINE_ROOT / "battle" / "c0m127.dat", battle / "c0m127.dat")


def states(page):
    return page.evaluate("""() => {
      const UI = window.LexeditorUI;
      const states = {};
      for (const [key, args] of [["none", {}], ["mod", {plugin: "ff8", modFile: "sfx/12.ogg"}],
          ["game", {plugin: "ff8", gameFile: "battle/c0m127.dat"}],
          ["both", {plugin: "ff8", modFile: "sfx/12.ogg", gameFile: "sfx/12.ogg"}]]) {
        const button = UI.fileLocationButton(args);
        states[key] = [button.disabled, button.title];
      }
      return states;
    }""")


def select(page, tab, selected, value):
    page.evaluate(f"state.selected.{selected}={value!r};navigate({tab!r})")
    page.wait_for_selector(".lex-detail-panel-actions .lex-file-location-button",
                           timeout=120000)


def header_button(page):
    button = page.locator(".lex-detail-panel-actions .lex-file-location-button")
    assert button.count() == 1
    return button


def no_mod_files(page):
    assert page.locator(".lex-detail-section-title",
                        has_text="MOD FILES").count() == 0


def main():
    with tempfile.TemporaryDirectory(prefix="lexeditor-file-location-") as project:
        seed(project)
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project}) as session, sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1600, "height": 1000})
            page.goto(session.url)
            page.wait_for_function("typeof state!=='undefined'&&!state.booting", timeout=90000)
            page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')", timeout=30000)
            found = states(page)
            assert found["none"] == [True, "No file to reveal"], found["none"]
            assert found["mod"] == [False, "Show the mod replacement in Explorer"], found["mod"]
            assert found["game"] == [False, "Show the shipped file in Explorer"], found["game"]
            assert found["both"][0] is False and "mod copy first" in found["both"][1], found["both"]
            select(page, "sfx", "sfx", 12)
            button = header_button(page)
            assert button.evaluate("node=>node.disabled") is False
            assert button.get_attribute("aria-label") == "Show the mod replacement in Explorer"  # the tooltip system rewrites title into data-lex-title
            no_mod_files(page)
            select(page, "sfx", "sfx", 0)
            assert header_button(page).evaluate("node=>node.disabled") is True
            select(page, "textures", "textures", "texl/0")
            button = header_button(page)
            assert button.evaluate("node=>node.disabled") is False
            assert button.get_attribute("aria-label") == "Show the mod replacement in Explorer"  # the tooltip system rewrites title into data-lex-title
            no_mod_files(page)
            select(page, "textures", "textures", "texl/1")
            assert header_button(page).evaluate("node=>node.disabled") is True
            select(page, "models", "models", "c0m127.dat")
            button = header_button(page)
            assert button.evaluate("node=>node.disabled") is False
            assert button.get_attribute("aria-label") == "Show the mod replacement in Explorer"  # the tooltip system rewrites title into data-lex-title
            browser.close()
            print("Asset detail headers carry the file-location button; MOD FILES sections are gone.")


if __name__ == "__main__":
    main()
