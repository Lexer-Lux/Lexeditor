"""Bare-field detail tabs spread across the reader's COLUMNS count.

DS1's item tabs (Armor Defense and the like) show one tab's bare properties,
not sections, in an unpaged flow. A stored single-column arrangement used to
pull every property back into the first column when the reader chose two, and
the emptied second column accepted no dragged property.
"""
from test_shared_ui_feedback import framework, page  # noqa: F401
from test_tab_rename import mount_shell

BUILD = """() => {
  const U = LexeditorUI;
  try { localStorage.clear(); } catch (_error) {}
  window.__fieldActive = 'defense';
  const rows = Array.from({length: 6}, (_, id) => ({id, name: 'Armor ' + id}));
  const fields = () => ['Physical', 'Slash', 'Strike', 'Thrust', 'Magic', 'Fire',
    'Lightning', 'Poison', 'Toxic', 'Bleed', 'Curse', 'Weight'].map(name => U.detailField({
      label: name, property: name.toLowerCase(),
      control: U.el('input', {type: 'number', value: 0, min: 0, max: 100})}));
  const main = document.querySelector('main');
  main.style.cssText = 'display:block;height:760px';
  window.__rebuildFields = () => main.replaceChildren(U.pagedListDetail({rows, key: row => row.id, selected: 0,
    noun: 'armor', splitKey: 'field-columns-check', slots: false, pageSize: 6, defaultSplit: 22,
    master: v => U.columnList({rows: v.rows, key: row => row.id, selected: v.selected, select: v.select,
      columns: [{key: 'name', label: 'Name'}]}),
    detail: row => U.detailPanel({title: row.name, body: [U.tabbedPanel({label: 'Item details',
      active: window.__fieldActive,
      tabs: [{id: 'defense', label: 'Defense'}, {id: 'basics', label: 'Basics'}],
      change: id => { window.__fieldActive = id; window.__rebuildFields(); },
      paginate: {unpaged: true}, content: fields()})]})}));
  window.__rebuildFields();
}"""

COLUMNS = """() => [...document.querySelectorAll('main .lex-tweaks-paged .lex-tweak-column')]
  .map(column => [...column.children].map(field => field.dataset.lexLayoutField))"""


def build(page):
    page.set_viewport_size({"width": 1700, "height": 800})
    framework(page)
    mount_shell(page, True)
    page.evaluate(BUILD)
    page.wait_for_timeout(400)


def set_columns(page, count):
    page.locator(".lex-list-detail-divider").first.hover()
    control = page.locator(".lex-list-detail-divider .lex-detail-column-control")
    for _ in range(8):
        current = int(control.locator(".lex-barrel-count").text_content())
        if current == count:
            break
        control.locator(".lex-barrel-increase" if current < count else ".lex-barrel-decrease").click()
        page.wait_for_timeout(200)
    page.wait_for_timeout(300)
    assert int(control.locator(".lex-barrel-count").text_content()) == count


def drag(page, name, target, bottom=False):
    source = page.locator('.lex-detail-field-label-text').filter(has_text=name)
    source.hover()
    box = target.bounding_box()
    source.drag_to(target, target_position={'x': 10, 'y': box['height'] - 2 if bottom else 2})
    page.wait_for_timeout(150)


def test_stored_single_column_order_spreads_across_two_columns(page):
    build(page)
    set_columns(page, 1)
    columns = page.evaluate(COLUMNS)
    assert len(columns) == 1 and len(columns[0]) == 12, columns
    drag(page, 'Slash', page.locator('[data-lex-layout-field="physical"]'))
    stored = page.evaluate(COLUMNS)
    assert stored == [['slash', 'physical', 'strike', 'thrust', 'magic', 'fire',
                       'lightning', 'poison', 'toxic', 'bleed', 'curse', 'weight']], stored
    set_columns(page, 2)
    spread = page.evaluate(COLUMNS)
    assert len(spread) == 2, spread
    assert all(spread), spread
    assert spread[0] + spread[1] == stored[0]


def test_developer_can_drop_a_property_into_an_empty_column(page):
    build(page)
    set_columns(page, 2)
    assert all(page.evaluate(COLUMNS))
    while True:
        columns = page.evaluate(COLUMNS)
        if len(columns) < 2 or not columns[1]:
            break
        name = page.locator(
            f'[data-lex-layout-field="{columns[1][0]}"] .lex-detail-field-label-text').text_content()
        first = page.locator('main .lex-tweak-column').first.locator('.lex-detail-field').first
        drag(page, name, first)
    assert page.evaluate(COLUMNS)[1] == []
    empty = page.locator('main .lex-tweaks-paged .lex-tweak-column').nth(1)
    box = empty.bounding_box()
    assert box and box['height'] > 0
    name = page.locator(
        '[data-lex-layout-field="physical"] .lex-detail-field-label-text').text_content()
    drag(page, name, empty)
    assert page.evaluate(COLUMNS)[1] == ['physical']
    page.evaluate("() => window.__rebuildFields()")
    page.wait_for_timeout(400)
    assert page.evaluate(COLUMNS)[1] == ['physical']
