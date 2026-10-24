"""The model-preview drawer starts below the heading on flex panels.

A detail panel whose body is one tabbed panel is flex, where the drawer's
grid row means nothing, so the drawer covered the whole panel with the
heading floating over its top rows: the enemy viewer's attack list lost
its first row under the heading. attachModelPreview now pins the
drawer's top edge to the heading's measured bottom edge.
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


def test_drawer_starts_below_heading_on_tabbed_panel():
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1100, "height": 800})
            page.route("http://fixture/**", lambda r: r.fulfill(
                body="<main></main>", content_type="text/html"))
            page.goto("http://fixture/")
            page.add_style_tag(path=str(ROOT / "ui/framework.css"))
            page.add_script_tag(path=str(ROOT / "ui/framework.js"))
            page.evaluate("""() => {
              const tabs = LexeditorUI.tabbedPanel({
                label: "Fixture", active: "a",
                tabs: [{id: "a", label: "A"}, {id: "b", label: "B"}],
                content: id => LexeditorUI.element("div", {}, `Tab ${id}`),
              });
              const panel = LexeditorUI.detailPanel({title: "Example", body: tabs});
              panel.style.cssText = 'width:700px;height:500px';
              const row = LexeditorUI.element("div", {"data-row": "first"});
              row.style.cssText = 'height:40px';
              row.textContent = "First row";
              LexeditorUI.attachModelPreview(panel, {
                content: () => LexeditorUI.stack({fill: true}, row,
                  LexeditorUI.element("div", {}, "Rest")),
              });
              document.querySelector("main").append(panel);
            }""")
            assert page.locator(".lex-detail-panel").evaluate(
                "n=>getComputedStyle(n).display") == "flex"
            page.get_by_role("button", name="Open model preview", exact=True).click()
            page.locator(".lex-model-preview-drawer").wait_for()
            gap = page.evaluate("""() => {
              const drawer = document.querySelector(".lex-model-preview-drawer");
              const heading = document.querySelector(".lex-detail-panel-heading");
              return drawer.getBoundingClientRect().top
                - heading.getBoundingClientRect().bottom;
            }""")
            assert abs(gap) <= 1, gap
            hit = page.evaluate("""() => {
              const row = document.querySelector('[data-row="first"]');
              const box = row.getBoundingClientRect();
              const at = document.elementFromPoint(
                box.left + box.width / 2, box.top + box.height / 2);
              return !!(at && (at === row || row.contains(at)));
            }""")
            assert hit, "the drawer's first row hides under the heading"
        finally:
            browser.close()
