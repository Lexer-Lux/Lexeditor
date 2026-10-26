"""An unbroken name wraps instead of shrinking its pane to the floor.

A 65-character token with no spaces overflowed its lane, and the uniform
fit dragged every label in the pane down to the 9px readability floor
trying to fit it - dragging the token to the bottom of a column left all
twelve labels stamped 9px. Label text may break inside an unbroken token,
so the token wraps to two lines and the pane keeps the size its names
need. Nothing truncates: the full token stays visible in its lane.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "shared"))

from test_detail_field_columns import (  # noqa: E402
    BUILD,
    COLUMNS,
    drag,
    set_columns,
)
from test_shared_ui_feedback import framework, page  # noqa: E402,F401
from test_tab_rename import mount_shell  # noqa: E402

TOKEN = ("SupercalifragilisticexpialidociousArmourPenetrationCoefficientValue")

SIZES = """() => [...document.querySelectorAll('.lex-detail-field-label')].map(label => ({
  size: getComputedStyle(label).fontSize, inline: label.style.fontSize || null,
  token: label.querySelector(':scope > .lex-detail-field-label-text')
    .textContent.startsWith('Supercalifragilistic'),
}))"""

TOKEN_BOX = """() => {
  const text = [...document.querySelectorAll('.lex-detail-field-label-text')]
    .find(t => t.textContent.startsWith('Supercalifragilistic'));
  const range = document.createRange(); range.selectNodeContents(text);
  return {lines: [...range.getClientRects()].filter(b => b.width && b.height).length,
    scrollW: text.scrollWidth, clientW: text.clientWidth,
    scrollH: text.scrollHeight, clientH: text.clientHeight};
}"""


def test_unbroken_token_wraps_and_keeps_pane_size(page):
    page.set_viewport_size({"width": 1700, "height": 800})
    framework(page)
    mount_shell(page, True)
    page.evaluate(BUILD)
    page.wait_for_timeout(400)
    page.evaluate("""(token) => {
      document.querySelector('[data-lex-layout-field="weight"] .lex-detail-field-label-text')
        .textContent = token;
    }""", TOKEN)
    page.wait_for_timeout(600)
    set_columns(page, 2)
    before = page.evaluate(SIZES)
    assert {row["size"] for row in before} == {"13px"}, before
    box = page.evaluate(TOKEN_BOX)
    assert box["lines"] == 2, box
    assert box["scrollW"] <= box["clientW"] + 1, box
    columns = page.evaluate(COLUMNS)
    name = page.locator(
        '[data-lex-layout-field="weight"] .lex-detail-field-label-text'
    ).text_content()
    target = page.locator("main .lex-tweak-column").nth(0).locator(".lex-detail-field").last
    drag(page, name, target, bottom=True)
    after = page.evaluate(COLUMNS)
    assert after[0][-1] == "weight", after
    sizes = page.evaluate(SIZES)
    assert {row["size"] for row in sizes} == {"13px"}, sizes
    box = page.evaluate(TOKEN_BOX)
    assert box["lines"] == 2, box
    assert box["scrollW"] <= box["clientW"] + 1, box
