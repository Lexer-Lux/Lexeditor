"""The tab strip keeps its first and last tab inside its own frame.

Lexer: "after looking at DS3 i can clearly see the outline of the leftmost tab
is cut off on the left. so the tabs bar seems to be somehow misaligned". It was:
a game whose theme set no navigation inset drew its first tab against the
window edge, so that tab's left edge - its outline and its rounded corner -
was painted against the frame instead of inside it. FF7, FF8 and FF9 set the
token; the other games were flush. The shared default is the panel gap now,
and a theme that wants edge-to-edge tabs can still say 0.
"""
from pathlib import Path
import re
import sys

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def test_a_theme_with_no_inset_still_keeps_the_first_tab_inside_the_strip():
    from plugins.blank.plugin import PLUGIN

    source = (ROOT / "ui" / "framework.css").read_text(encoding="utf-8")
    assert not re.search(r"padding-inline:\s*var\(--lex-nav-padding-inline,\s*0px\)", source), (
        "a strip with no inset draws its first tab against the window edge")

    session = PLUGIN.session_factory()
    session.start()
    try:
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1440, "height": 900})
                page.goto(session.url, wait_until="domcontentloaded")
                page.wait_for_selector(".lex-shell-header nav button")
                page.wait_for_timeout(400)
                measured = page.evaluate("""()=>{
                  const frame=document.querySelector('.lex-nav-frame'),
                    buttons=[...document.querySelectorAll('.lex-shell-header nav button')],
                    css=getComputedStyle(frame),
                    box=frame.getBoundingClientRect(),
                    contentLeft=box.left+parseFloat(css.borderLeftWidth)+parseFloat(css.paddingLeft),
                    contentRight=box.right-parseFloat(css.borderRightWidth)-parseFloat(css.paddingRight),
                    first=buttons[0].getBoundingClientRect(),
                    last=buttons[buttons.length-1].getBoundingClientRect();
                  return {firstLeft:first.left, contentLeft, contentRight,
                    lastRight:last.right, tabs:buttons.length,
                    scrollLeft:frame.scrollLeft,
                    scrollable:frame.scrollWidth>frame.clientWidth+1};}""")
                assert measured["tabs"] >= 2, measured
                # The first tab's left edge, and the last tab's right edge, are
                # inside the frame the strip scrolls in.
                assert measured["firstLeft"] >= measured["contentLeft"] - 0.5, measured
                assert measured["firstLeft"] <= measured["contentLeft"] + 2, measured
                assert measured["lastRight"] <= measured["contentRight"] + 0.5, measured
                assert measured["scrollLeft"] == 0, measured
            finally:
                browser.close()
    finally:
        session.stop()
