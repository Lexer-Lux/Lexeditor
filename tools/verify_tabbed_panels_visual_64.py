"""Hidden rendered proof for the shared tabbed-panel control and FF8 use."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))

from games.blank.plugin import BlankSession  # noqa: E402
from games.ff8.plugin import FF8Session  # noqa: E402
from render_crime_editors_55_62 import wait_eval  # noqa: E402
from tools.verify_panel_layout_visual_46 import (  # noqa: E402
    browser_session, close_browser, screenshot,
)


def verify_blank() -> dict:
    profile = browser = cdp = None
    try:
        profile, browser, cdp = browser_session()
        with BlankSession() as session:
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof navigate==='function'", 30)
            cdp.eval("navigate('subtabs')")
            wait_eval(cdp, "document.querySelectorAll('.blank-subtab-panel [role=tab]').length===3", 30)
            cdp.eval("document.querySelectorAll('.blank-subtab-panel [role=tab]')[1].click()")
            wait_eval(cdp, "document.querySelector('.blank-subtab-panel [role=tab][aria-selected=true]')?.textContent.includes('References')", 10)
            result = cdp.eval("""(()=>{const panel=document.querySelector('.blank-subtab-panel');
              const tabs=[...panel.querySelectorAll('[role=tab]')];return{
                tabs:tabs.map(node=>node.textContent.trim().replace(/\\d+$/,'')),
                active:panel.querySelector('[role=tab][aria-selected=true]')?.textContent.trim().replace(/\\d+$/,''),
                panel:panel.getBoundingClientRect().toJSON(),
                content:panel.querySelector('.lex-tabbed-panel-content')?.getBoundingClientRect().toJSON(),
              }})()""")
            assert result["tabs"] == ["Controls", "References", "States"], result
            assert result["active"] == "References", result
            assert result["content"]["height"] > 0 and result["content"]["width"] > 0, result
            result["screenshot"] = str(screenshot(cdp, "github-64-blank-tabbed-panel.png"))
            return result
    finally:
        if profile:
            close_browser(profile, browser, cdp)


def verify_ff8() -> dict:
    project = tempfile.TemporaryDirectory(prefix="lexeditor-tabbed-ff8-", ignore_cleanup_errors=True)
    profile = browser = cdp = None
    try:
        profile, browser, cdp = browser_session()
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
            cdp.eval("state.selected.enemies=state.data.enemyTables.rows[0].id;navigate('enemies')")
            wait_eval(cdp, "document.querySelectorAll('.enemy-tabbed-column [role=tab]').length===3", 30)
            cdp.eval("[...document.querySelectorAll('.enemy-tabbed-column [role=tab]')].find(node=>node.textContent.includes('AI')).click()")
            wait_eval(cdp, "document.querySelectorAll('.enemy-ability-table .lex-column-list-row').length===48", 30)
            result = cdp.eval("""(()=>{const panel=document.querySelector('.enemy-tabbed-column'),
              table=panel.querySelector('.enemy-ability-table'),pr=panel.getBoundingClientRect(),tr=table.getBoundingClientRect();return{
                active:panel.querySelector('[role=tab][aria-selected=true]')?.textContent.trim().replace(/\\d+$/,''),
                rows:panel.querySelectorAll('.enemy-ability-table .lex-column-list-row').length,
                tiers:[...panel.querySelectorAll('.enemy-table-section>h3')].map(node=>node.textContent.trim()),
                horizontalOverflow:tr.width>pr.width+1,
                clippedControls:[...panel.querySelectorAll('select,input')].filter(node=>node.scrollWidth>node.clientWidth+1).length,
              }})()""")
            assert result["active"] == "AI" and result["rows"] == 48, result
            assert result["tiers"] == ["LOW LEVEL", "MEDIUM LEVEL", "HIGH LEVEL"], result
            assert not result["horizontalOverflow"] and result["clippedControls"] == 0, result
            result["screenshot"] = str(screenshot(cdp, "github-64-ff8-enemy-ai.png"))
            return result
    finally:
        if profile:
            close_browser(profile, browser, cdp)
        project.cleanup()


def main() -> int:
    print({"blank": verify_blank(), "ff8": verify_ff8()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
