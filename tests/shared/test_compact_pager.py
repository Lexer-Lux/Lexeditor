"""The compact pagination bar: pager's narrow-panel variant.

Search on its own row up top, no X-Y/Z position count, the toggle label
reading bottom-to-top, and everything left sharing one bottom row instead
of stacking. Mounted in the DS1 maps directory's 360px panel.
"""
from test_shared_ui_feedback import page, framework  # noqa: F401


MOUNT = """(narrow) => {
  const U = LexeditorUI;
  const host = U.el("div", {id: "narrow",
    style: "width:360px;display:flex;flex-direction:column;"});
  document.querySelector("main").replaceChildren(host);
  window.compactChanges = [];
  window.compactSearches = [];
  host.append(U.compactPager({page: 1, pages: 4, total: 80, pageSize: 20,
    search: {key: "compact-fixture", label: "Search the world", value: "",
      change: value => window.compactSearches.push(value)},
    filters: [U.pagerToggle({label: "Local?", checked: false, change: () => {}})],
    rowControl: {value: 20, defaultValue: 20, overridden: false,
      change: value => window.compactChanges.push("rows:" + value)},
    change: value => window.compactChanges.push(value)}));
  return document.querySelector(".lex-compact-pager") !== null;
}"""


def mount(page):
    framework(page)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    assert page.evaluate(MOUNT) is True
    page.wait_for_selector(".lex-compact-pager")
    return errors


def test_search_sits_on_its_own_row_with_no_position_count(page):
    errors = mount(page)
    assert page.locator(".lex-compact-pager .lex-page-summary").count() == 0
    search = page.locator(".lex-compact-pager-search").bounding_box()
    bottom = page.locator(".lex-compact-pager-bottom").bounding_box()
    assert search["y"] + search["height"] <= bottom["y"] + 1, (search, bottom)
    assert page.get_by_role("searchbox", name="Search the world").count() == 1
    assert errors == []


def test_everything_left_shares_one_bottom_row(page):
    mount(page)
    boxes = page.locator(".lex-compact-pager-bottom > *").evaluate_all(
        "nodes => nodes.map(node => { const box = node.getBoundingClientRect();"
        " return {x: box.x, y: box.y, width: box.width, height: box.height}; })")
    assert len(boxes) >= 3, boxes
    middle = page.locator(".lex-compact-pager-bottom").bounding_box()
    midline = middle["y"] + middle["height"] / 2
    # One visual row: every child straddles the row's middle line and each
    # child starts where the previous one ends (nothing wrapped below).
    for box in boxes:
        assert box["y"] <= midline <= box["y"] + box["height"], (box, midline)
    for left, right in zip(boxes, boxes[1:]):
        assert right["x"] >= left["x"] + left["width"] - 2, (left, right)
    assert page.locator(".lex-compact-pager .lex-pager-controls").count() == 1
    assert page.locator(".lex-compact-pager [data-lex-view-filter], "
                        ".lex-compact-pager .lex-pager-toggle").count() >= 1


def test_toggle_label_reads_bottom_to_top(page):
    mount(page)
    label = page.locator(".lex-compact-pager .lex-pager-toggle > span")
    assert label.count() == 1
    assert label.evaluate("node => getComputedStyle(node).writingMode") == "vertical-rl"
    assert label.evaluate("node => getComputedStyle(node).transform") != "none"
    box = label.bounding_box()
    assert box["width"] < box["height"], box


def test_paging_and_search_still_drive_changes(page):
    errors = mount(page)
    page.locator(".lex-compact-pager").get_by_role("button", name="Next page").click()
    assert page.evaluate("window.compactChanges") == [2]
    page.get_by_role("searchbox", name="Search the world").fill("burg")
    assert page.evaluate("window.compactSearches") == ["burg"]
    assert errors == []


def test_single_page_keeps_filters_on_the_row_without_controls(page):
    framework(page)
    page.evaluate("""() => {
      const U = LexeditorUI;
      document.querySelector("main").replaceChildren(
        U.compactPager({page: 0, pages: 1, total: 3, pageSize: 20,
          filters: [U.pagerToggle({label: "Local?", checked: false, change: () => {}})],
          change: () => {}}));
    }""")
    bar = page.locator(".lex-compact-pager")
    assert bar.count() == 1
    assert bar.locator(".lex-pager-controls").count() == 0
    assert bar.locator(".lex-compact-pager-bottom .lex-pager-toggle").count() == 1
