"""A record's header preview pins as a table column like any property.

The master list declares no fixed picture column: pinning the header
thumbnail (or right-clicking it) adds the pin:icon column with the
game's own cell render, an empty header, and no sorting. Unpinning
removes it again.
"""
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
