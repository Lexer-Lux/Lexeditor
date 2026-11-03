"""No FF8 record detail paginates, however narrow the panel gets.

Every record tab renders its detail at a small viewport; no detail may
show the section pager footer. Details flow and scroll instead. (The
Tweaks card grid keeps its own paging and is not a record detail.)
"""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from playwright.sync_api import sync_playwright
from plugins.ff8.plugin import FF8Session

TABS = ["items", "weapons", "abilities", "characters", "enemies", "gfs",
        "sfx", "models", "textures", "text", "refine", "shops", "fields",
        "world", "encounters", "cards"]


# Shops shows its stock as a bare table with no detail panel; nothing there
# can page, so the guard waits for the stock list instead of a panel.
WAIT = {"shops": ".lex-column-list"}


def assert_no_detail_pager(page, where):
    page.wait_for_selector(WAIT.get(where, ".lex-detail-panel, .lex-tabbed-panel"),
                           timeout=180000)
    page.wait_for_timeout(1500)
    found = page.locator("#main .lex-tweaks-pages .lex-pager").count()
    assert found == 0, f"{where}: {found} detail pager(s)"


def main():
    with tempfile.TemporaryDirectory(prefix="lexeditor-no-detail-pager-") as project:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project}) as session, sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 700, "height": 700})
            page.goto(session.url)
            page.wait_for_function("typeof state!=='undefined'&&!state.booting", timeout=90000)
            page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')", timeout=30000)
            for tab in TABS:
                print("tab:", tab, flush=True)
                page.evaluate(f"navigate({tab!r})")
                assert_no_detail_pager(page, tab)
            for mode in ("decks", "players"):
                page.locator(".lex-subtab-bar button", has_text=mode.upper()).click()
                assert_no_detail_pager(page, f"cards/{mode}")
            browser.close()
            print(f"All {len(TABS)} record tabs plus card decks/players show no detail pager.")


if __name__ == "__main__":
    main()
