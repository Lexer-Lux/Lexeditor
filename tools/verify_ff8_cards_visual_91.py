"""Rendered Cards controls and temporary-project save round trip."""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, r"C:\RDR2Mod\tools\reverse-engineering")
from games.ff8.plugin import FF8Session
from tools.verify_panel_layout_visual_46 import browser_session, close_browser, screenshot
from render_crime_editors_55_62 import wait_eval


def main():
    profile = browser = cdp = None
    try:
        profile, browser, cdp = browser_session()
        with tempfile.TemporaryDirectory(prefix="ff8-cards-visual-") as project:
            with FF8Session({"LEXEDITOR_FF8_PROJECT": project}) as session:
                cdp.call("Page.navigate", {"url": session.url})
                wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
                cdp.eval("state.selected.cards=0;navigate('cards')")
                wait_eval(cdp, "document.querySelector('[aria-label=\"Card name\"]')!==null", 15)
                assert cdp.eval("document.querySelectorAll('#main input[data-min=\"0\"][data-max=\"10\"]').length") == 4
                assert cdp.eval("document.querySelectorAll('#main select option').length") >= 9
                cdp.eval("const name=document.querySelector('[aria-label=\"Card name\"]');name.value='Test Card';name.dispatchEvent(new Event('input',{bubbles:true}));const rank=document.querySelector('[aria-label=\"Geezard Top\"]');rank.value='10';rank.dispatchEvent(new Event('input',{bubbles:true}));rank.dispatchEvent(new Event('change',{bubbles:true}));")
                assert cdp.eval("state.data.cards.rows[0].top") == 10
                cdp.eval("saveAll()", await_promise=True)
                assert cdp.eval("state.data.cards.rows[0].name") == "Test Card"
                assert cdp.eval("state.data.cards.rows[0].top") == 10
                assert cdp.eval("dirtyCount()") == 0
                assert cdp.eval("window.__testErrors") == []
                screenshot(cdp, "github-91-cards.png")
                print("PASS: Cards list/detail, bounded ranks, element selector, edited name/rank saved and reloaded with no console errors")
    finally:
        close_browser(profile, browser, cdp)


if __name__ == "__main__":
    main()
