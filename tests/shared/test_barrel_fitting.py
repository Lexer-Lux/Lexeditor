"""Barrels of one table share column widths and ask for content width.

Each barrel used to fit only its own rows: a long value in one barrel
("Split archive" in Kind) squeezed that barrel's other columns while its
neighbours stayed wide. The master pane also stayed at its floor while
names truncated and the detail pane sat empty. Pinning a column rebuilt
the barrels without refitting the layout, so the new column squeezed in.
"""
from test_shared_ui_feedback import framework, page

PAGE = """() => {
  const U = LexeditorUI;
  try { localStorage.clear(); } catch (_error) {}
  window.state = {selected: 1, page: 0};
  const rows = Array.from({length: 20}, (_, index) => ({id: index + 1,
    name: `tex${String(index).padStart(2, '0')}_diffuse.dds`,
    values: {kind: index, origin: index},
    display: {kind: index >= 10 ? 'Split archive' : 'Textures',
      origin: 'Highlands'}}));
  let view = null;
  const render = () => {
    view = U.pagedListDetail({rows, key: row => row.id, selected: state.selected,
      slots: true, noun: 'textures', pageSize: 10, page: state.page, rowsKey: 'barrel-fitting',
      defaultSplit: 22,
      change: next => {
        if (next.reason === 'pins' && view?.refreshMaster) view.refreshMaster();
        else { state.page = next.page; render(); }
      },
      master: ({rows: listed, selected, select}) => U.columnList({rows: listed,
        key: row => row.id, selected, select,
        columns: [{key: 'name', label: 'Name', grow: 1},
          {key: 'kind', label: 'Kind', render: row => row.display.kind}]}),
      detail: row => U.detailPanel({title: row.name, body: [U.detailSection({title: 'File', body: [
        U.detailField({label: 'Kind', property: 'kind',
          control: U.el('input', {value: row.display.kind})}),
        U.detailField({label: 'Origin', property: 'origin',
          control: U.el('input', {value: row.display.origin})})]})]}),
    });
    document.querySelector('main').replaceChildren(view);
  };
  render();
}"""

TEMPLATES = """() => [...document.querySelectorAll('.lex-barrel-grid > .lex-column-list')]
  .map(n => n.style.getPropertyValue('--lex-column-list-template'))"""

KIND_WIDTHS = """() => [...document.querySelectorAll('.lex-barrel-grid > .lex-column-list')]
  .map(n => Math.round(n.querySelector('.lex-column-list-row:not(.lex-filler-row)'
    + ' [data-column-key="kind"]').getBoundingClientRect().width))"""

TRUNCATED = """() => [...document.querySelectorAll('.lex-barrel-grid'
  + ' .lex-column-list-row:not(.lex-filler-row) [data-column-key="name"] .lex-column-cell-text')]
  .filter(n => n.scrollWidth > n.clientWidth + 1).length"""

MASTER_WIDTH = """() => Math.round(document.querySelector('.lex-barrelled-master')
  .getBoundingClientRect().width)"""


def build(page):
    page.set_viewport_size({"width": 2000, "height": 900})
    framework(page)
    # The theme font loads asynchronously; settle it before building so
    # column widths do not flap mid-test.
    page.wait_for_function("document.fonts.status === 'loaded'")
    page.wait_for_timeout(300)
    page.evaluate(PAGE)
    page.wait_for_timeout(500)


def add_barrels(page, count):
    plus = page.locator('.lex-barrel-control:not(.lex-detail-column-control) .lex-barrel-increase')
    for _ in range(count):
        plus.click(force=True)
        page.wait_for_timeout(400)
    page.wait_for_function(
        "() => document.querySelectorAll('.lex-barrel-grid > .lex-column-list').length === 2")
    page.wait_for_function(
        "() => { const templates = [...document.querySelectorAll('.lex-barrel-grid > .lex-column-list')]"
        ".map(n => n.style.getPropertyValue('--lex-column-list-template'));"
        " return templates.length === 2 && templates.every(t => t === templates[0]); }")


def test_barrels_share_column_widths_and_fit_names(page):
    build(page)
    add_barrels(page, 1)
    assert page.evaluate(KIND_WIDTHS) == [page.evaluate(KIND_WIDTHS)[0]] * 2
    assert page.evaluate(TRUNCATED) == 0


PINNED_TRUNCATED = """() => [...document.querySelectorAll('.lex-barrel-grid'
  + ' .lex-column-list-row:not(.lex-filler-row) [data-column-key="pin:origin"] .lex-column-cell-text')]
  .filter(n => n.scrollWidth > n.clientWidth + 1).length"""

KIND_TRUNCATED = """() => [...document.querySelectorAll('.lex-barrel-grid'
  + ' .lex-column-list-row:not(.lex-filler-row) [data-column-key="kind"] .lex-column-cell-text')]
  .filter(n => n.scrollWidth > n.clientWidth + 1).length"""


def test_pinning_a_column_refits_the_master(page):
    build(page)
    add_barrels(page, 1)
    before = page.evaluate(MASTER_WIDTH)
    page.locator('[data-lex-pin-column="origin"]').click(force=True)
    page.wait_for_function("() => document.querySelectorAll('.lex-column-list-head-cell"
                           + "[data-column-key=\"pin:origin\"]').length === 2")
    page.wait_for_timeout(800)
    # The pin sticks: without the refit the crowded new column is refused.
    assert page.locator('[data-lex-pin-column="origin"]').get_attribute("aria-pressed") == "true"
    templates = page.evaluate(TEMPLATES)
    assert all(t == templates[0] for t in templates), templates
    assert page.evaluate(PINNED_TRUNCATED) == 0
    assert page.evaluate(KIND_TRUNCATED) == 0
    assert page.evaluate(TRUNCATED) == 0
    assert page.evaluate(MASTER_WIDTH) > before
