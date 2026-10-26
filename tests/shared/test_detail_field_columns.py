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


def summon_columns(page):
    # Summon like a reader: hover the divider strip, not the parked gizmo.
    # Parked it is invisible, click-through, and rotated, with its center
    # deep in pane territory where pane content covers it; the strip is
    # the reveal zone, and the gizmo opens under the cursor at mid-height.
    page.locator(".lex-list-detail-divider").hover()


def set_columns(page, count):
    summon_columns(page)
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

def tally(page):
    summon_columns(page)
    return page.locator(
        ".lex-list-detail-divider .lex-detail-column-control .lex-barrel-count").text_content()


def test_tally_counts_empty_fitted_columns(page):
    # A fitted deal whose stored layout stacks everything left keeps its
    # empty columns taking their share of the row. The tally used to count
    # non-empty columns, so it read "1" on a three-column deal: minus sat
    # disabled while drops landed in the "missing" columns. It reads the
    # effective deal instead.
    build(page)
    set_columns(page, 3)
    assert tally(page) == "3"
    while True:
        columns = page.evaluate(COLUMNS)
        if len(columns) < 3 or (not columns[1] and not columns[2]):
            break
        donor = 1 if columns[1] else 2
        name = page.locator(
            f'[data-lex-layout-field="{columns[donor][0]}"] .lex-detail-field-label-text').text_content()
        first = page.locator('main .lex-tweak-column').first.locator('.lex-detail-field').first
        drag(page, name, first)
    assert page.evaluate(COLUMNS)[1:] == [[], []]
    # Right-click fits to width again: the deal keeps three columns (the
    # stored three-group layout applies as stored), and the tally says so.
    summon_columns(page)
    control = page.locator(".lex-list-detail-divider .lex-detail-column-control")
    control.hover()
    control.click(button="right")
    page.wait_for_timeout(400)
    columns = page.evaluate(COLUMNS)
    assert len(columns) == 3, columns
    assert columns[1:] == [[], []], columns
    assert tally(page) == "3"
    assert page.locator(
        ".lex-list-detail-divider .lex-detail-column-control .lex-barrel-decrease").is_enabled()

SCOPED_BUILD = """([barrel, columnsKey]) => {
  const U = LexeditorUI;
  try { localStorage.clear(); } catch (_error) {}
  const rows = Array.from({length: 6}, (_, id) => ({id, name: 'Ammo ' + id}));
  const fields = () => ['Damage', 'Weight', 'Price'].map(name => U.detailField({
    label: name, property: name.toLowerCase(),
    control: U.el('input', {type: 'number', value: 0, min: 0, max: 100})}));
  const main = document.querySelector('main');
  main.style.cssText = 'display:block;height:760px';
  window.__scopedBuild = barrelNow => main.replaceChildren(U.pagedListDetail({rows,
    key: row => row.id, selected: 0, noun: 'ammo', splitKey: 'scope-check', slots: false,
    pageSize: 6, defaultSplit: 22, barrelKey: barrelNow, columnsKey,
    master: v => U.columnList({rows: v.rows, key: row => row.id, selected: v.selected,
      select: v.select, columns: [{key: 'name', label: 'Name'}]}),
    detail: row => U.detailPanel({title: row.name, body: fields()})}));
  window.__scopedBuild(barrel);
}"""


def build_scoped(page, barrel, columns_key):
    page.set_viewport_size({"width": 1700, "height": 800})
    framework(page)
    mount_shell(page, True)
    page.evaluate(SCOPED_BUILD, [barrel, columns_key])
    page.wait_for_timeout(400)


def test_columns_key_shares_count_across_subtab_barrels(page):
    # DS1 renders every record tab through one paged list whose barrel key
    # carries the subtab, so a count change in Ammo never reached
    # Consumables while dragged properties did. A shared columnsKey keeps
    # one count per tab across its subtabs.
    build_scoped(page, 'ds1-items-ammo', 'ds1-items')
    assert tally(page) == "1"
    set_columns(page, 3)
    page.evaluate("() => window.__scopedBuild('ds1-items-consumables')")
    page.wait_for_timeout(400)
    assert tally(page) == "3"


def test_barrel_scoped_counts_stay_independent(page):
    # Without a columnsKey the count stays per barrel key, so unrelated
    # lists keep their own counts as before.
    build_scoped(page, 'scope-list-a', None)
    set_columns(page, 3)
    page.evaluate("() => window.__scopedBuild('scope-list-b')")
    page.wait_for_timeout(400)
    assert tally(page) == "1"

SUBTAB_BUILD = """([key]) => {
  const U = LexeditorUI;
  window.__shareActive = 'weapons';
  const rows = Array.from({length: 6}, (_, id) => ({id, name: 'Ammo ' + id}));
  const fields = () => ['Damage', 'Weight', 'Price'].map(name => U.detailField({
    label: name, property: name.toLowerCase(),
    control: U.el('input', {type: 'number', value: 0, min: 0, max: 100})}));
  const main = document.querySelector('main');
  main.style.cssText = 'display:block;height:760px';
  window.__shareBuild = () => main.replaceChildren(U.pagedListDetail({rows,
    key: row => row.id, selected: 0, noun: 'ammo', splitKey: 'share-check',
    slots: false, pageSize: 6, defaultSplit: 22, columnsKey: key,
    master: v => U.columnList({rows: v.rows, key: row => row.id, selected: v.selected,
      select: v.select, columns: [{key: 'name', label: 'Name'}]}),
    detail: row => U.detailPanel({title: row.name, body: [U.tabbedPanel({label: 'Item details',
      active: window.__shareActive,
      tabs: [{id: 'weapons', label: 'Weapons'}, {id: 'ammo', label: 'Ammo'}],
      change: id => { window.__shareActive = id; window.__shareBuild(); },
      paginate: {unpaged: true}, content: fields()})]})}));
  window.__shareBuild();
}"""


def build_subtabs(page, columns_key):
    page.set_viewport_size({"width": 1700, "height": 800})
    framework(page)
    mount_shell(page, True)
    page.evaluate(SUBTAB_BUILD, [columns_key])
    page.wait_for_timeout(400)


def column_keys(page):
    return page.evaluate("""() => {
      const out = [];
      for (let index = 0; index < localStorage.length; index++) {
        const key = localStorage.key(index);
        if (key && key.startsWith('lexeditor:columns:')) out.push(key);
      }
      return out.sort();
    }""")


def test_shared_columns_key_ignores_the_subtab_path(page):
    # Lexer: defense shows four columns under Weapons and three under
    # Ammo. DS1 passes one columnsKey per tab so every subtab shares a
    # count, but the live subtab path extended that key anyway and split
    # it again. A shared key stays whole across subtab switches.
    build_subtabs(page, "shared-tabs")
    set_columns(page, 1)
    assert tally(page) == "1"
    page.locator('.lex-subtab-button[data-subtab="ammo"]').click()
    page.wait_for_timeout(400)
    assert tally(page) == "1"
    assert column_keys(page) == ["lexeditor:columns:shared-tabs"]


def test_default_columns_key_stays_per_subtab(page):
    # Without an explicit columnsKey nothing changes: unrelated tabs
    # keep their own counts.
    build_subtabs(page, None)
    set_columns(page, 1)
    assert tally(page) == "1"
    page.locator('.lex-subtab-button[data-subtab="ammo"]').click()
    page.wait_for_timeout(400)
    assert tally(page) != "1"


def test_per_subtab_counts_migrate_to_the_shared_key(page):
    # Counts saved under older per-subtab keys move up once: the current
    # subtab's wins, and the dead keys go away. Each test gets a fresh
    # profile, so the seeds planted before the build are the whole store,
    # the way a reader's older keys predate the shared one.
    page.set_viewport_size({"width": 1700, "height": 800})
    framework(page)
    mount_shell(page, True)
    page.evaluate("""() => {
      localStorage.setItem('lexeditor:columns:migrate-tabs:weapons', '4');
      localStorage.setItem('lexeditor:columns:migrate-tabs:ammo', '3');
    }""")
    page.evaluate(SUBTAB_BUILD, ["migrate-tabs"])
    page.wait_for_timeout(400)
    assert tally(page) == "4"
    assert column_keys(page) == ["lexeditor:columns:migrate-tabs"]
    assert page.evaluate(
        "() => localStorage.getItem('lexeditor:columns:migrate-tabs')") == "4"
