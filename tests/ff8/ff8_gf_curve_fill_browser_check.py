"""A lone graph fills its GF tab instead of ending halfway down.

The HP and XP tabs each hold one curve editor; the plot stretches to
the tab content's full height, leaving no empty gray below it.
"""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from playwright.sync_api import sync_playwright
from plugins.ff8.plugin import FF8Session


def fill(page):
    return page.evaluate("""() => {
      const panel = document.querySelector(".lex-tabbed-panel");
      const content = panel.querySelector(":scope > .lex-tabbed-panel-content");
      const plot = content.querySelector(":scope > .lex-curve-editor > .lex-curve-plot");
      const box = content.getBoundingClientRect(), drawn = plot.getBoundingClientRect();
      return {content: box.height, plot: drawn.height,
              gap: box.bottom - drawn.bottom};
    }""")


def main():
    with tempfile.TemporaryDirectory(prefix="lexeditor-gf-curve-") as project:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project}) as session, sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1600, "height": 1000})
            page.goto(session.url)
            page.wait_for_function("typeof state!=='undefined'&&!state.booting", timeout=90000)
            page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')", timeout=30000)
            page.evaluate("state.gfDetailTab='hp';navigate('gfs')")
            page.wait_for_selector(".lex-curve-plot", timeout=120000)
            page.wait_for_timeout(1000)
            state = fill(page)
            assert state["gap"] <= 8, state
            assert state["plot"] >= state["content"] - 8, state
            page.locator(".lex-tabbed-panel [role='tab']", has_text="XP").first.click()
            page.wait_for_timeout(1000)
            state = fill(page)
            assert state["gap"] <= 8, state
            assert state["plot"] >= state["content"] - 8, state
            browser.close()
            print("GF HP and XP graphs fill their tabs.")


if __name__ == "__main__":
    main()
