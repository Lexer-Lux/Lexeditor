"""Field doors, exits and triggers are their table, edge to edge.

Each of the three tabs hands its bare table to the tab content, so the
grid fills the panel with no wrapper margins. A table taller than its
content scrolls inside itself with a sticky header.
"""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from playwright.sync_api import sync_playwright
from plugins.ff8.plugin import FF8Session

SUBS = ["doors", "exits", "triggers"]


def geometry(page):
    return page.evaluate("""() => {
      const panel = document.querySelector(".lex-tabbed-panel");
      const content = panel.querySelector(":scope > .lex-tabbed-panel-content");
      const table = content.querySelector(":scope > .lex-column-list");
      const box = el => { const rect = el.getBoundingClientRect();
        return [Math.round(rect.width), Math.round(rect.height)]; };
      const style = getComputedStyle(table);
      return {content: box(content), table: box(table), bare: !!table,
              over: [table.scrollHeight, table.clientHeight],
              scroll: style.overflowY,
              sticky: getComputedStyle(table.querySelector(
                ":scope > .lex-column-list-header")).position};
    }""")


def main():
    with tempfile.TemporaryDirectory(prefix="lexeditor-field-tables-") as project:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project}) as session, sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1600, "height": 1000})
            page.goto(session.url)
            page.wait_for_function("typeof state!=='undefined'&&!state.booting", timeout=90000)
            page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')", timeout=30000)
            for sub in SUBS:
                page.evaluate(f"state.fieldDetailTab='{sub}';navigate('fields')")
                page.wait_for_selector(".lex-tabbed-panel .lex-column-list", timeout=180000)
                page.wait_for_timeout(1500)
                state = geometry(page)
                assert state["bare"] is True, (sub, state)
                assert state["table"] == state["content"], (sub, state)
                assert state["scroll"] == "auto", (sub, state)
                assert state["sticky"] == "sticky", (sub, state)
            page.set_viewport_size({"width": 1600, "height": 420})
            page.wait_for_timeout(1500)
            state = geometry(page)
            assert state["over"][0] > state["over"][1], state
            page.evaluate("""() => { const table = document.querySelector(
              ".lex-tabbed-panel-content > .lex-column-list");
              table.scrollTop = table.scrollHeight; }""")
            page.wait_for_timeout(500)
            pinned = page.evaluate("""() => {
              const content = document.querySelector(".lex-tabbed-panel-content");
              const head = content.querySelector(
                ":scope > .lex-column-list > .lex-column-list-header");
              return Math.round(head.getBoundingClientRect().top) -
                     Math.round(content.getBoundingClientRect().top);
            }""")
            assert pinned <= 1, pinned
            browser.close()
            print("Doors, exits and triggers fill their panel and scroll with a sticky header.")


if __name__ == "__main__":
    main()
