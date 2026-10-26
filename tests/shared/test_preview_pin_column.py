"""A record's header preview pins as a table column like any property.

The master list declares no fixed picture column: pinning the header
thumbnail (or right-clicking it) adds the pin:icon column with the
game's own cell render, an empty header, and no sorting. Unpinning
removes it again.

The pinned picture also fills its square cell at any row count: the
column track follows the fitted row height, so the icon must scale
with it at 20 and at 40 rows/page alike.
"""
import pytest

from test_shared_ui_feedback import framework, page

PAGE = """() => {
  const U = LexeditorUI;
  localStorage.clear();
  window.state = {selected: 1, page: 0};
  const rows = [
    {id: 1, name: 'Alpha', values: {power: 70}},
    {id: 2, name: 'Beta', values: {power: 90}},
  ];
  const picture = () => U.el('span', {class: 'probe-picture'}, '#');
  let view = null;
  const render = () => {
    view = U.pagedListDetail({
      rows, key: row => row.id, selected: state.selected, slots: false, noun: 'probes',
      page: state.page, rowsKey: 'preview-pin-probes',
      change: next => {
        if (next.reason === 'pins' && view?.refreshMaster) view.refreshMaster();
        else { state.page = next.page; render(); }
      },
      master: ({rows: listed, selected, select}) => U.columnList({rows: listed,
        key: row => row.id, selected, select, columns: [{key: 'name', label: 'Name'}]}),
      describePinnedCell: key => key === 'icon'
        ? {editable: false, label: '', sortable: false, width: '36px',
           render: row => U.el('span', {class: 'probe-cell'}, picture())}
        : {editable: false, label: key},
      detail: row => U.detailPanel({title: row.name, icon: picture(),
        previewPin: {key: 'icon', label: 'Icon'},
        body: [U.detailSection({title: 'Stats', body: [
          U.detailField({label: 'Power', property: 'power',
            control: U.el('input', {value: row.values.power})})]})]}),
    });
    document.querySelector('main').replaceChildren(view);
  };
  render();
}"""

HEADS = """() => [...document.querySelectorAll(
  '.lex-column-list-head-cell')].map(h => h.textContent.trim())"""


def test_header_preview_pin_adds_and_removes_the_picture_column(page):
    framework(page)
    page.evaluate(PAGE)
    page.wait_for_timeout(500)
    assert 'pin:icon' not in str(page.evaluate(
        "() => [...document.querySelectorAll('.lex-column-list-head-cell')]"
        ".map(h => h.dataset.columnKey)"))
    pin = page.locator('.lex-detail-panel-icon > .lex-column-pin')
    assert pin.count() == 1
    assert 'pinned' not in (pin.get_attribute('class') or '')
    pin.click(force=True)
    page.wait_for_timeout(500)
    keys = page.evaluate(
        "() => [...document.querySelectorAll('.lex-column-list-head-cell')]"
        ".map(h => h.dataset.columnKey)")
    assert 'pin:icon' in keys, keys
    head = page.locator('.lex-column-list-head-cell[data-column-key="pin:icon"]')
    assert head.inner_text().strip() == '', head.inner_text()
    assert page.locator('.lex-column-list .probe-cell').count() == 2
    before = page.locator('.lex-column-list .lex-list-row').all_inner_texts()
    head.click(force=True)
    page.wait_for_timeout(300)
    assert page.locator('.lex-column-list .lex-list-row').all_inner_texts() == before
    page.locator('.lex-detail-panel-icon').click(button='right')
    page.wait_for_timeout(500)
    keys = page.evaluate(
        "() => [...document.querySelectorAll('.lex-column-list-head-cell')]"
        ".map(h => h.dataset.columnKey)")
    assert 'pin:icon' not in keys, keys


# A portrait picture like a DS1 menu icon (160x180), drawn inline so the
# test needs no game files.
ICON_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' width='160' height='180'>"
    "<rect width='160' height='180' fill='#a4824c'/></svg>"
)

PIN_FILL_PAGE = """(args) => {
  const U = LexeditorUI, main = document.querySelector('main');
  localStorage.clear();
  main.style.height = '90vh';
  localStorage.setItem('lexeditor:pins:pin-fill-probes',
    JSON.stringify([{key: 'icon', label: 'Icon'}]));
  const rows = Array.from({length: 80}, (_, id) => ({id, name: 'Record ' + id}));
  const icon = () => {
    const picture = document.createElement('img');
    picture.src = 'data:image/svg+xml,' + encodeURIComponent(args.svg);
    picture.alt = '';
    picture.draggable = false;
    return picture;
  };
  main.replaceChildren(U.pagedListDetail({
    rows, key: row => row.id, selected: 0, noun: 'records',
    rowsKey: 'pin-fill-probes', slots: false, pageSize: args.pageSize,
    change: () => {},
    master: v => U.columnList({rows: v.rows, key: row => row.id, selected: v.selected,
      columns: [{key: 'name', label: 'Name', sortable: true, grow: 1}]}),
    describePinnedCell: key => key === 'icon'
      ? {editable: false, label: '', sortable: false,
         width: 'var(--lex-fitted-row-height,36px)', render: icon}
      : {editable: false, label: key},
    detail: row => U.detailPanel({title: row.name}),
  }));
}"""

PIN_FILL_METRICS = """() => {
  const fitted = parseFloat(getComputedStyle(
    document.querySelector('.lex-column-list'))
    .getPropertyValue('--lex-fitted-row-height'));
  const rows = [...document.querySelectorAll(
    '.lex-column-list-row:not(.lex-filler-row)')].map(row => {
    const box = row.getBoundingClientRect();
    const cell = row.querySelector('.lex-column-list-cell[data-column-key="pin:icon"]');
    const img = cell.querySelector('img');
    const art = img.getBoundingClientRect();
    const lane = cell.getBoundingClientRect();
    return {row: box.height, icon: art.height,
            iconWidth: art.width, cell: lane.width};
  });
  return {fitted, rows};
}"""


@pytest.mark.parametrize('page_size', [20, 40])
def test_pinned_icon_fills_its_square_cell(page, page_size):
    """The pinned picture column fills its square cell at any row count.

    At 40 rows/page the pinned icon used to collapse to nothing while
    20 rows left gaps, because the shared icon sizing only matched the
    fixed icon column and never the pin:icon one.
    """
    framework(page)
    page.evaluate(PIN_FILL_PAGE, {'svg': ICON_SVG, 'pageSize': page_size})
    page.wait_for_function(
        "document.querySelector('.lex-column-list-row img')?.naturalWidth > 0")
    page.wait_for_function(
        "getComputedStyle(document.querySelector('.lex-column-list'))"
        ".getPropertyValue('--lex-fitted-row-height').trim() !== ''")
    page.wait_for_timeout(500)  # the fitter settles after fonts load
    metrics = page.evaluate(PIN_FILL_METRICS)
    assert len(metrics['rows']) == page_size, (len(metrics['rows']), page_size)
    for entry in metrics['rows']:
        assert abs(entry['row'] - metrics['fitted']) <= 1, (entry, metrics['fitted'])
        assert abs(entry['cell'] - entry['row']) <= 3, entry
        # 0.69, not 0.70: sub-pixel rounding puts a 70% floor at 0.6998.
        assert entry['icon'] / entry['row'] >= 0.69, entry
        assert abs(entry['iconWidth'] / entry['icon'] - 160 / 180) < 0.05, entry
