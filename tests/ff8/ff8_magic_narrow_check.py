"""A Magic record squeezed to its narrowest panel keeps every switch whole.

Lexer: "MAGIC -> left panel: i can make this panel so thin that the text pops
out of its boolean box and the element type icons get cut off."

A J-Element value and its element flags were two parts side by side. The flags'
part kept an empty label column and the provenance rail beside them, so at the
panel's minimum each element switch was 25px wide: its type rail hung outside
the box and its icon was cut to a pixel. This drags the list/detail divider as
far as it goes and checks, on both tabs, that every switch's rail, icon and
name sit inside its own box.
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))

from plugins.ff8.plugin import FF8Session  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from tests.shared.verify_panel_layout_visual_46 import (  # noqa: E402
    browser_session, close_browser, screenshot, wait_eval,
)

SWITCHES = """(()=>{const panel=document.querySelector('.magic-detail');
  const toggles=[...panel.querySelectorAll('.lex-toggle')].filter(t=>t.getBoundingClientRect().width);
  const bad=toggles.filter(t=>{const box=t.getBoundingClientRect(),name=t.querySelector('.lex-toggle-name');
    return (name&&name.scrollWidth>name.clientWidth+1)||[...t.querySelectorAll('.lex-toggle-rail,img,.lex-toggle-name')]
      .some(part=>{const b=part.getBoundingClientRect();return b.width&&(b.left<box.left-1||b.right>box.right+1||b.width<6)})})
    .map(t=>t.textContent.trim());
  return {panel:Math.round(panel.getBoundingClientRect().width),switches:toggles.length,
    icons:panel.querySelectorAll('.lex-toggle img').length,bad}})()"""


def main() -> int:
    project = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-magic-narrow-",
                                          ignore_cleanup_errors=True)
    profile = browser = cdp = None
    try:
        profile, browser, cdp = browser_session()
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 120)
            cdp.eval("navigate('magic')")
            wait_eval(cdp, "document.querySelector('.magic-detail')!==null", 30)
            divider = cdp.eval("""(()=>{const box=document.querySelector('.lex-list-detail-divider').getBoundingClientRect();
              return [box.left+box.width/2,box.top+box.height/2]})()""")
            x, y = divider
            cdp.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "buttons": 1, "clickCount": 1})
            for step in range(1, 21):
                cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x + step * 60, "y": y, "button": "left", "buttons": 1})
            cdp.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x + 1200, "y": y, "button": "left", "buttons": 0, "clickCount": 1})
            time.sleep(0.5)
            results = {}
            for tab in ("Attack", "Junction"):
                cdp.eval(f"""[...document.querySelectorAll('.magic-detail [role=tab]')]
                  .find(t=>t.textContent.toLowerCase().includes({tab.lower()!r}))?.click()""")
                time.sleep(0.5)
                results[tab] = cdp.eval(SWITCHES)
                assert results[tab]["switches"] > 0 and not results[tab]["bad"], (tab, results[tab])
            assert results["Junction"]["icons"] >= 16, results
            image = screenshot(cdp, "ff8-magic-narrow.png")
            print(json.dumps({"results": results, "screenshot": str(image)}))
        return 0
    finally:
        if profile:
            close_browser(profile, browser, cdp)
        project.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
