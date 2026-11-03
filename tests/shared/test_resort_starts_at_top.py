"""A new sort shows the list from its first page.

Lexer: "you never fixed the god damn sorting". A header click re-sorted the
rows, then the list jumped back to whichever page held the selected record,
so the sorted order was shown from somewhere in its middle.
"""
from test_shared_ui_feedback import page, framework


MOUNT = '''() => {
  const U = LexeditorUI;
  const rows = Array.from({length: 60}, (_, id) => ({id, name: 'Row ' + String(id).padStart(2, '0'), power: (id * 37) % 60}));
  const view = {page: 0, selected: 45, sort: {key: 'name', dir: 1}};
  const draw = () => {
    const sorted = [...rows].sort((a, b) => U.compareRecords(a, b, view.sort) || a.id - b.id);
    document.querySelector('main').replaceChildren(U.pagedListDetail({rows: sorted, key: r => r.id,
      selected: view.selected, page: view.page, pageSize: 10, splitKey: 'resort', slots: false,
      search: {value: '', input() {}},
      change: next => { view.page = next.page; view.selected = next.selected; draw(); },
      sync: next => { view.page = next.page; view.selected = next.selected; },
      master: v => U.columnList({rows: v.rows, key: r => r.id, selected: v.selected, sortState: view.sort,
        sort: key => { view.sort = {key, dir: view.sort.key === key ? -view.sort.dir : 1}; draw(); },
        columns: [{key: 'name', label: 'Name'}, {key: 'power', label: 'Power'}]}),
      detail: r => U.detailPanel({title: r.name})}));
  };
  window.view = view;
  draw();
}'''


def test_a_header_click_shows_the_new_order_from_its_first_row(page):
    framework(page)
    page.evaluate(MOUNT)
    assert page.evaluate("view.page") == 4, "the selected record's page"
    page.locator(".lex-column-list-head-cell", has_text="Power").click()
    page.wait_for_timeout(100)
    first = page.locator(".lex-column-list-cell[data-column-key='power']").first.text_content().strip()
    assert page.evaluate("view.page") == 0
    assert first == "0", first
    # Paging afterwards is the reader's again, and a later re-render does not
    # jump anywhere on its own.
    page.evaluate("view.page = 2; view.selected = null")
    page.evaluate(MOUNT.replace("draw();\n}", "view.page = 2; draw();\n}"))
    assert page.evaluate("view.page") == 2
