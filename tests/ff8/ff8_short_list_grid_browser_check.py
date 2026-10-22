"""A short master page keeps its grid to the bottom of the panel.

Shops page two holds five real shops; empty filler rows square off the
page with the same cells, rules and background as real rows, so the list
ends in a spreadsheet grid instead of flat gray. Real rows still select.
"""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from playwright.sync_api import sync_playwright
from plugins.ff8.plugin import FF8Session


def grid_state(page):
    return page.evaluate("""() => {
      const table = document.querySelector(".lex-column-list[data-lex-barrel]");
      const real = [...table.querySelectorAll(":scope > .lex-column-list-row[data-key]")];
      const fill = [...table.querySelectorAll(":scope > .lex-filler-row")];
      const heads = table.querySelectorAll(
        ":scope > .lex-column-list-header > .lex-column-list-head-cell").length;
      const border = cell => getComputedStyle(cell).borderRightColor;
      const first = fill[0];
      const cells = first ? [...first.querySelectorAll(":scope > .lex-column-list-cell")] : [];
      const last = fill[fill.length - 1];
      return {real: real.length, fill: fill.length, heads,
              cells: cells.length,
              hidden: first?.getAttribute("aria-hidden"),
              pointer: first ? getComputedStyle(first).pointerEvents : null,
              rule: cells.length ? border(cells[0]) : null,
              realRule: real.length
                ? border(real[0].querySelector(":scope > .lex-column-list-cell")) : null,
              reach: last ? table.getBoundingClientRect().bottom -
                last.getBoundingClientRect().bottom : null,
              row: last ? last.getBoundingClientRect().height : null};
    }""")


def main():
    with tempfile.TemporaryDirectory(prefix="lexeditor-short-grid-") as project:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project}) as session, sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1600, "height": 1000})
            page.goto(session.url)
            page.wait_for_function("typeof state!=='undefined'&&!state.booting", timeout=90000)
            page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')", timeout=30000)
            page.evaluate("navigate('shops')")
            page.wait_for_selector(".lex-column-list", timeout=120000)
            page.locator(".lex-pager button", has_text=">").first.click()
            page.wait_for_timeout(1500)
            state = grid_state(page)
            assert state["real"] == 5, state
            assert state["fill"] > 0, state
            assert state["cells"] == state["heads"] == 2, state
            assert state["hidden"] == "true", state
            assert state["pointer"] == "none", state
            assert state["rule"] == state["realRule"], state
            assert state["rule"] != "rgba(0, 0, 0, 0)", state
            assert 0 <= state["reach"] <= state["row"], state
            first = page.locator(".lex-column-list[data-lex-barrel] "
                               ".lex-column-list-row[data-key]").first
            key = first.get_attribute("data-key")
            first.click()
            page.wait_for_function(f"String(state.selected.shops)==={key!r}", timeout=30000)
            browser.close()
            print("Short pages pad with ruled filler rows; real rows still select.")


if __name__ == "__main__":
    main()
