"""A column sort orders the whole list, and the sorted column shows its mark.

Blank draws the shared UI with no game installed, so it is the reference page
for both halves of a report from Lexer: sorting a page-sized table reordered
the rows on screen and left the rest of the list alone, and the mark that says
which column is sorted was missing in every game without the FF8-style skin.

The mark was drawn against the header row instead of the label it belongs to,
so it sat at the row's far left and the header cell's own overflow hid it. Both
are measured here in the browser, across pages, because neither is visible in
the source.
"""

from __future__ import annotations

# Dev caches and outputs live in the temp folder, never in the checkout.
DEV_CACHE = __import__("pathlib").Path(__import__("tempfile").gettempdir()) / "lexeditor-dev"
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plugins.blank.plugin import PLUGIN  # noqa: E402


# The component catalogue is a paged list whose master table declares no sort
# of its own, so the shared paged list has to own the order.
LIST = ".blank-components"
TABLE = f"{LIST} .lex-barrelled-master"
HEAD = f'{TABLE} .lex-column-list-head-cell[data-column-key="id"]'
ROWS = f"{TABLE} .lex-column-list-row"


def main() -> int:
    shot = DEV_CACHE / "table-sort.png"
    DEV_CACHE.mkdir(parents=True, exist_ok=True)
    session = PLUGIN.session_factory()
    session.start()
    failures: list[str] = []
    seen: dict[str, object] = {}
    try:
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1500, "height": 950})
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(session.url, wait_until="domcontentloaded")
            page.wait_for_timeout(1600)

            def pager(label: str) -> bool:
                """Press one pager button, ignoring a disabled end-of-list one."""
                control = page.locator(f'{LIST} [aria-label="{label}"]')
                if not control.count() or control.is_disabled():
                    return False
                control.click()
                page.wait_for_timeout(300)
                return True

            def page_ids() -> list[str]:
                return page.evaluate(
                    """selector => [...document.querySelectorAll(selector)]
                        .map(row => row.querySelector('[data-column-key="id"]')
                          ?.textContent.trim())
                        .filter(Boolean)""", ROWS)

            def all_ids() -> list[str]:
                """Every component, in the order the list really shows them."""
                ids: list[str] = []
                while pager("First page"):
                    pass
                while True:
                    ids += page_ids()
                    if not pager("Next page"):
                        break
                while pager("First page"):
                    pass
                return ids

            def mark() -> dict:
                return page.evaluate(
                    """selector => {
                      const cell = document.querySelector(selector);
                      const indicator = cell?.querySelector('.lex-sort-indicator');
                      if (!indicator) return {};
                      const cellBox = cell.getBoundingClientRect();
                      const markBox = indicator.getBoundingClientRect();
                      return {sorted: cell.classList.contains('sorted'),
                              descending: indicator.classList.contains('descending'),
                              width: Number(markBox.width.toFixed(2)),
                              insideCell: markBox.left >= cellBox.left - 0.5
                                && markBox.right <= cellBox.right + 0.5,
                              leftOfWords: markBox.right
                                <= cell.querySelector('.header-label').getBoundingClientRect().left + 0.5};
                    }""", HEAD)

            lower = str.lower
            before = all_ids()
            seen["rows"] = len(before)
            if len(before) < 20:
                failures.append(f"only {len(before)} catalogue rows to page through")
            if before == sorted(before, key=lower):
                failures.append("the catalogue starts in order, so a page-only sort cannot show")
            if len(before) != len(set(before)):
                failures.append("the same component was listed twice across pages")

            page.locator(HEAD).click()
            page.wait_for_timeout(600)
            ascending_mark = mark()
            ascending = all_ids()
            seen["ascendingMark"] = ascending_mark
            if ascending != sorted(ascending, key=lower):
                failures.append(f"sorting by Component left {len(ascending)} rows out of order")
            if ascending_mark.get("descending"):
                failures.append("the first click on an unsorted column was not ascending")
            if not ascending_mark.get("sorted"):
                failures.append("the sorted column is not marked as sorted")
            if not ascending_mark.get("width"):
                failures.append("the sorted column draws no sort mark")
            if ascending_mark.get("sorted") and not ascending_mark.get("insideCell"):
                failures.append("the sort mark is drawn outside the header cell, so it is cut off")
            if ascending_mark.get("sorted") and not ascending_mark.get("leftOfWords"):
                failures.append("the sort mark is not on the label's left, where the column words are")

            page.locator(HEAD).click()
            page.wait_for_timeout(600)
            descending_mark = mark()
            descending = all_ids()
            seen["descendingMark"] = descending_mark
            if descending != sorted(ascending, key=lower, reverse=True):
                failures.append("the second click did not reverse the whole list")
            if not descending_mark.get("descending"):
                failures.append("the mark does not turn over for the reversed order")
            if not descending_mark.get("insideCell"):
                failures.append("the reversed sort mark is drawn outside the header cell")

            # Leave the page sorted the way the screenshot should read.
            page.locator(HEAD).click()
            page.wait_for_timeout(400)
            page.screenshot(path=str(shot))
            if errors:
                failures.append(f"the page threw: {errors[:3]}")
            browser.close()
    finally:
        session.stop()

    report = {"rows": seen.get("rows"), "ascending": seen.get("ascendingMark"),
              "descending": seen.get("descendingMark"), "failures": failures,
              "screenshot": str(shot)}
    print(json.dumps(report, indent=1))
    if failures:
        print("Table sorting check failed:")
        for line in failures:
            print(" -", line)
        return 1
    print(f"Sorting {seen.get('rows', 0)} rows across pages keeps one order and shows its mark.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
