"""Hidden Edge proof for the shared filled-circle help marker (GitHub #56)."""

from __future__ import annotations

from pathlib import Path
import shutil
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
RDR2_ROOT = Path(r"C:\RDR2Mod")
sys.path.insert(0, str(ROOT))

from games.ff8.plugin import FF8Session  # noqa: E402
from games.rdr2.plugin import Rdr2Session  # noqa: E402
from tools.verify_panel_layout_visual_46 import (  # noqa: E402
    browser_session, close_browser, screenshot,
)
from render_crime_editors_55_62 import wait_eval  # noqa: E402


def marker_geometry(cdp, selector: str) -> dict:
    return cdp.eval(f"""(()=>{{const node=document.querySelector({selector!r}),
      child=node.firstElementChild,box=node.getBoundingClientRect(),inner=child.getBoundingClientRect(),
      style=getComputedStyle(node);node.focus();node.dispatchEvent(new PointerEvent('pointerenter',{{bubbles:true}}));const popup=document.querySelector('.lex-help-popover');return{{tag:node.tagName,text:node.textContent,
      title:node.title,aria:node.getAttribute('aria-label'),popup:popup?.textContent,width:box.width,height:box.height,radius:style.borderRadius,
      fill:style.backgroundColor,border:style.borderTopWidth,
      centerDelta:Math.max(Math.abs((box.left+box.width/2)-(inner.left+inner.width/2)),
        Math.abs((box.top+box.height/2)-(inner.top+inner.height/2))),
      focused:document.activeElement===node}};}})()""")


def assert_marker(marker: dict) -> None:
    assert marker["text"] == "?" and not marker["title"], marker
    assert marker["aria"] and marker["popup"] == marker["aria"], marker
    assert marker["width"] == marker["height"] == 18, marker
    assert marker["radius"] == "50%" and marker["border"] == "0px", marker
    assert marker["fill"] not in ("rgba(0, 0, 0, 0)", "transparent"), marker
    assert marker["centerDelta"] <= 1.1 and marker["focused"], marker


def verify_ff8() -> dict:
    project = tempfile.TemporaryDirectory(prefix="lexeditor-info-help-ff8-", ignore_cleanup_errors=True)
    profile = browser = cdp = None
    try:
        profile, browser, cdp = browser_session()
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
            cdp.eval("navigate('shops')")
            wait_eval(cdp, "!!document.querySelector('.ff8-shop-table .lex-info-help')", 30)
            marker = marker_geometry(cdp, ".ff8-shop-table .lex-info-help")
            assert_marker(marker)
            marker["screenshot"] = str(screenshot(cdp, "github-56-ff8-filled-help.png"))
            return marker
    finally:
        if profile:
            close_browser(profile, browser, cdp)
        project.cleanup()


def verify_rdr2() -> dict:
    isolated = tempfile.TemporaryDirectory(prefix="lexeditor-info-help-rdr2-", ignore_cleanup_errors=True)
    profile = browser = cdp = None
    try:
        temp_ini = Path(isolated.name) / "GameplayTweaks.ini"
        shutil.copy2(RDR2_ROOT / "GameplayTweaks" / "GameplayTweaks.ini", temp_ini)
        profile, browser, cdp = browser_session()
        with Rdr2Session({
            "LEXEDITOR_GAMEPLAY_INI": str(temp_ini),
            "RDR2_GAME_ROOT": str(Path(isolated.name) / "empty-game-root"),
        }) as session:
            cdp.call("Page.navigate", {"url": session.url + "#settings"})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting&&state.tab==='settings'", 90)
            cdp.eval("(async()=>{await renderSettings();window.scrollTo(0,0);return true})()", True)
            wait_eval(cdp, "!!document.querySelector('.settings-field .lex-info-help')", 30)
            marker = marker_geometry(cdp, ".settings-field .lex-info-help")
            assert_marker(marker)
            marker["screenshot"] = str(screenshot(cdp, "github-56-rdr2-filled-help.png"))
            return marker
    finally:
        if profile:
            close_browser(profile, browser, cdp)
        isolated.cleanup()


def main() -> int:
    print({"ff8": verify_ff8(), "rdr2": verify_rdr2()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
