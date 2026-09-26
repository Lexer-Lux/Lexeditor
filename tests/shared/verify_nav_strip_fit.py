"""Every page tab keeps its whole name, and the row is still filled.

Lexer: "the amount of side margin on tab names is still obscenely huge ... the
'Tweaks' text takes up only like half the width of the tab" and "so many cut off
text bugs ... i thought you said you could give me testers to ensure it didn't
happen". Two rules answer both: a tab is never narrower than its own name, and
the whole strip shrinks together into the window instead of clipping one label
or scrolling. This measures the rendered strip of a real plugin page.

FF8 is the hard case - twenty tabs in the game's wide lettering, wider than the
window at the theme's own size - and Blank is the easy one, five short names
that must still spread across the row. FF7 is left out on purpose: its editor
page is written into the served HTML and this harness never gives its frame an
animation frame, so its strip cannot be measured from here.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from plugins.blank.plugin import BlankSession  # noqa: E402
from plugins.ff8.plugin import FF8Session  # noqa: E402
from render_crime_editors_55_62 import wait_eval  # noqa: E402
from verify_panel_layout_visual_46 import browser_session, close_browser  # noqa: E402

MEASURE = """(()=>{
  const nav=document.querySelector('.lex-shell-header nav'),
    frame=document.querySelector('.lex-nav-frame');
  if(!nav||!frame) return {found:false};
  const labels=[...nav.querySelectorAll('.lex-tab-label-text')],
    buttons=[...nav.querySelectorAll('button[data-tab]')];
  const text=label=>{const range=document.createRange();
    range.selectNodeContents(label);return range.getBoundingClientRect().width;};
  return {found:true, tabs:buttons.length,
    lane:nav.clientWidth, strip:nav.scrollWidth,
    frameScrolls:frame.scrollWidth>frame.clientWidth+1,
    fonts:[...new Set(labels.map(l=>Math.round(
      parseFloat(getComputedStyle(l).fontSize)*100)/100))],
    clipped:labels.filter(l=>l.scrollWidth>l.clientWidth+1)
      .map(l=>l.textContent.trim()),
    swallowed:buttons.filter((b,i)=>text(labels[i])>b.getBoundingClientRect().width-8)
      .map(b=>b.textContent.trim())};})()"""


def measure(session, widths, ready):
    """Open the plugin's own page and measure its strip at each width."""
    profile, browser, cdp = browser_session()
    rows = {}
    try:
        cdp.call("Page.navigate", {"url": session.url})
        wait_eval(cdp, ready, 180)
        cdp.eval("new Promise(resolve=>setTimeout(resolve,900))", True)
        for width in widths:
            cdp.call("Emulation.setDeviceMetricsOverride",
                     {"width": width, "height": 900, "deviceScaleFactor": 1,
                      "mobile": False})
            cdp.eval("new Promise(resolve=>setTimeout(resolve,700))", True)
            cdp.eval("dispatchEvent(new Event('resize'))")
            cdp.eval("new Promise(resolve=>setTimeout(resolve,700))", True)
            rows[width] = cdp.eval(MEASURE)
    finally:
        close_browser(profile, browser, cdp)
    return rows


def test_ff8_twenty_tabs_fit_one_row():
    with tempfile.TemporaryDirectory(prefix="lexeditor-navstrip-ff8-") as project:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project}) as session:
            rows = measure(session, (1600, 1280),
                           "typeof state!=='undefined'&&!state.booting")
    for width, row in rows.items():
        assert row["found"], row
        assert row["tabs"] == 20, (width, row)
        assert not row["clipped"], (width, row)
        assert len(row["fonts"]) == 1, (width, row)
        # The strip fills the lane the frame leaves it and stops there, so the
        # row is used and there is nothing to scroll.
        assert row["strip"] >= row["lane"], (width, row)
        assert row["strip"] <= row["lane"] + 1, (width, row)
        assert not row["frameScrolls"], (width, row)
        assert row["fonts"][0] >= 9, (width, row)


def test_blank_tabs_share_the_row():
    with BlankSession() as session:
        rows = measure(session, (1600,),
                       "!!document.querySelector('.lex-shell-header nav')")
    row = rows[1600]
    assert row["found"], row
    assert row["tabs"] == 5, row
    assert not row["clipped"], row
    assert not row["swallowed"], row
    assert row["strip"] >= row["lane"], row
    assert row["strip"] <= row["lane"] + 1, row
    assert not row["frameScrolls"], row


if __name__ == "__main__":
    raise SystemExit(__import__("pytest").main([__file__, "-q"]))
