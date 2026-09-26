"""The editor header's own controls are one set, on one centre line.

Lexer: "the buttons in the menu bar are all different. different position,
different gap, different order". They were: Save and Play were pinned two
pixels larger than their neighbours by an id rule, and the round menu buttons
two pixels smaller by their own cap, so a row that centres its contents still
painted three different top edges.
"""
from pathlib import Path
import sys

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def test_every_command_row_control_shares_one_height_and_centre():
    from plugins.blank.plugin import PLUGIN

    session = PLUGIN.session_factory()
    session.start()
    try:
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1440, "height": 900})
                page.goto(session.url, wait_until="domcontentloaded")
                page.wait_for_selector(".lex-shell-command-row button")
                page.wait_for_timeout(400)
                # The wordmark is a label that answers a click, not a control:
                # its height is its text's. Everything else in the row is one
                # set of controls.
                controls = page.evaluate("""()=>[...document.querySelectorAll('.lex-shell-command-row button')]
                  .filter(node=>node.offsetParent!==null && !node.classList.contains('lex-brand-button'))
                  .map(node=>{const r=node.getBoundingClientRect();
                    return {cls:String(node.className).slice(0,44),height:Math.round(r.height*10)/10,
                      centre:Math.round((r.top+r.height/2)*10)/10};})""")
                assert len(controls) >= 6, controls
                heights = {row["height"] for row in controls}
                centres = {row["centre"] for row in controls}
                assert len(heights) == 1, controls
                assert len(centres) == 1, controls
            finally:
                browser.close()
    finally:
        session.stop()
