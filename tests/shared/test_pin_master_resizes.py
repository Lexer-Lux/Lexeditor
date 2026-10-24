"""The master list auto-resizes for pinned columns, both directions.

Pinning columns into a short table used to ratchet the master wider on
every toggle and never give the room back: filler rows (which hold no
values) measured their stretched box as content, element cell content
measured its box instead of its text, the panel shares kept what the old
columns needed, and content-sized columns undercounted their headers, so
pins were refused while spare room sat untouched. The master now grows
for pins, refuses only when genuinely crowded, and restores exactly.
"""
from test_shared_ui_feedback import framework, page

PAGE = """() => {
  const U = LexeditorUI;
  localStorage.clear();
  window.state = {selected: 1, page: 0};
  const rows = [
    {id: 1, name: 'Dagger of the Betrayed', values: {power: 70, kind: 3, weight: 12, durability: 40, range: 8}},
    {id: 2, name: 'Club', values: {power: 90, kind: 1, weight: 30, durability: 55, range: 4}},
  ];
  let view = null;
  const render = () => {
    view = U.pagedListDetail({
      rows, key: row => row.id, selected: state.selected, slots: false, noun: 'weapons',
      page: state.page, rowsKey: 'pinfit-weapons',
      change: next => {
        if (next.reason === 'pins' && view?.refreshMaster) view.refreshMaster();
        else { state.page = next.page; render(); }
      },
      master: ({rows: listed, selected, select}) => U.columnList({rows: listed, key: row => row.id, selected, select,
        columns: [{key: 'name', label: 'Name',
          render: row => U.el('a', {href: '#', onclick: event => event.preventDefault()}, row.name)}]}),
      detail: row => U.detailPanel({title: row.name, body: [U.detailSection({title: 'Stats', body: [
        U.detailField({label: 'Power', property: 'power', control: U.el('input', {value: row.values.power})}),
        U.detailField({label: 'Kind', property: 'kind', control: U.el('input', {value: row.values.kind})}),
        U.detailField({label: 'Weight', property: 'weight', control: U.el('input', {value: row.values.weight})}),
        U.detailField({label: 'Durability', property: 'durability', control: U.el('input', {value: row.values.durability})}),
        U.detailField({label: 'Range', property: 'range', control: U.el('input', {value: row.values.range})})]})]}),
    });
    document.querySelector('main').replaceChildren(view);
  };
  render();
}"""

WIDTH = """() => ({
  master: document.querySelector('.lex-barrelled-master').getBoundingClientRect().width,
  pins: document.querySelectorAll('.lex-column-list-head-cell[data-column-key^="pin:"]').length,
  overflow: (() => {
    const list = document.querySelector('.lex-barrelled-master .lex-column-list');
    return list.scrollWidth - list.clientWidth;
  })(),
})"""


def test_pin_cycle_grows_and_restores_the_master(page):
    framework(page)
    page.evaluate(PAGE)
    page.wait_for_timeout(500)
    base = page.evaluate(WIDTH)
    assert base['pins'] == 0, base
    assert base['overflow'] <= 1, base
    for prop in ('power', 'kind', 'weight', 'durability', 'range'):
        page.locator(f'[data-lex-pin-column="{prop}"]').click(force=True)
        page.wait_for_timeout(450)
    grown = page.evaluate(WIDTH)
    assert grown['pins'] == 5, grown
    assert grown['overflow'] <= 1, grown
    assert grown['master'] > base['master'] + 30, (base, grown)
    for prop in ('power', 'kind', 'weight', 'durability', 'range'):
        page.locator(f'[data-lex-pin-column="{prop}"]').click(force=True)
        page.wait_for_timeout(450)
    page.wait_for_timeout(400)
    restored = page.evaluate(WIDTH)
    assert restored['pins'] == 0, restored
    assert abs(restored['master'] - base['master']) <= 4, (base, restored)
