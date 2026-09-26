"""Hovering a field's own picture hides its overlaid map name entirely.

Lexer: "field: make it so the map name text fades to nothing when the top-right
panel is hovered. currently it just goes semitransparent."

The field preview overlays the map's name on its own picture and the shared rule
fades that heading to 15% on hover, which leaves a ghost of the name. This opens
the real Field page from the installed game, hovers the picture, and checks the
overlaid heading's opacity is now zero rather than a faint 0.15.
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


def main() -> int:
    project = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-field-fade-",
                                          ignore_cleanup_errors=True)
    profile = browser = cdp = None
    try:
        profile, browser, cdp = browser_session()
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 120)
            cdp.eval("navigate('fields')")
            wait_eval(cdp, "document.querySelector('.field-map-detail.lex-detail-panel-media')!==null", 60)
            selector = ".field-map-detail .lex-detail-panel-heading"
            rest = cdp.eval(f"getComputedStyle(document.querySelector({selector!r})).opacity")
            assert rest == "1", rest
            center = cdp.eval("""(()=>{const node=document.querySelector('.field-map-detail.lex-detail-panel-media');
              const box=node.getBoundingClientRect();
              return [box.left+box.width/2, box.top+box.height/2]})()""")
            x, y = center
            cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x - 4, "y": y - 4,
                                                  "buttons": 0, "button": "none"})
            cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y,
                                                  "buttons": 0, "button": "none"})
            time.sleep(0.4)
            hovering = cdp.eval("document.querySelector('.field-map-detail.lex-detail-panel-media').matches(':hover')")
            assert hovering, hovering
            hovered = cdp.eval(f"getComputedStyle(document.querySelector({selector!r})).opacity")
            assert hovered == "0", hovered
            image = screenshot(cdp, "ff8-field-name-fade.png")
            print(json.dumps({"restOpacity": rest, "hoverOpacity": hovered,
                              "screenshot": str(image)}))
        return 0
    finally:
        if profile:
            close_browser(profile, browser, cdp)
        project.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
