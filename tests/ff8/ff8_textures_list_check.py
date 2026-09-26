"""The Textures list shows each texture's whole name, and its caveat is help.

Checking Lexer's Textures note ("hovering a thumbnail should ... expand") turned
up the page itself: a max-content Size column ("128 x 128 . 8-bit . 1 pal") took
287px and left the Texture column a 38px stub, so every name read "*-"; and a
battle texture's caveat ("Replace the whole model file on the Models tab ...")
sat as a paragraph in the panel body. This renders the real page at 1600px and
checks no list cell is cut and the only note in the panel is the empty state.
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
    project = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-textures-",
                                          ignore_cleanup_errors=True)
    profile = browser = cdp = None
    try:
        profile, browser, cdp = browser_session()
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 120)
            cdp.eval("navigate('textures')")
            wait_eval(cdp, "document.querySelector('.ff8-record-list .lex-column-list-row')!==null", 60)
            time.sleep(0.5)
            result = cdp.eval("""(()=>{const list=document.querySelector('.ff8-record-list');
              const cut=[...list.querySelectorAll('.lex-column-list-row *')]
                .filter(node=>!node.children.length&&node.scrollWidth>node.clientWidth+1).map(node=>node.textContent);
              const name=list.querySelector('.lex-column-list-row .lex-column-list-cell[data-column-key="name"]');
              return {cut,nameWidth:Math.round(name.getBoundingClientRect().width),
                notes:[...document.querySelectorAll('.lex-detail-panel .lex-detail-note')].map(note=>note.textContent.trim()),
                help:!!document.querySelector('.lex-detail-panel .lex-detail-section .lex-info-help')}})()""")
            assert not result["cut"], result
            assert result["nameWidth"] >= 240, result
            assert all(note == "No mod replaces this texture." for note in result["notes"]), result
            image = screenshot(cdp, "ff8-textures-list.png")
            print(json.dumps({**result, "screenshot": str(image)}))
        return 0
    finally:
        if profile:
            close_browser(profile, browser, cdp)
        project.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
