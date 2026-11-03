"""Section headers drag between columns, and the arrangement sticks.

DS1's Drops tab deals Drop sections into columns by height. A stored
arrangement used to keep only the reading order, so dragging Drop 2 under
Drop 1 (already next in reading order) stored nothing and sprang back, and
adding a column re-flowed every section. Drops now pin section->column
lanes: the deal honors them, widening leaves sections put, and narrowing
clamps the extra lanes into the last column.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_shared_ui_feedback import framework, page  # noqa: F401,E402
from test_tab_rename import mount_shell  # noqa: E402
from test_detail_field_columns import set_columns  # noqa: E402

BUILD = """() => {
  const U = LexeditorUI;
  try { localStorage.clear(); } catch (_error) {}
  window.__sectionActive = 'drops';
  const rows = Array.from({length: 6}, (_, id) => ({id, name: 'Lot ' + id}));
  const fields = (tag, count) => Array.from({length: count}, (_, i) => U.detailField({
    label: `${tag} field ${i + 1}`, property: `${tag}-${i + 1}`,
    control: U.el('input', {type: 'number', value: 0})}));
  const sections = () => [U.detailSection({title: 'Drop 1', body: fields('one', 8)}),
    U.detailSection({title: 'Drop 2', body: fields('two', 2)}),
    U.detailSection({title: 'Drop 3', body: fields('three', 2)}),
    U.detailSection({title: 'Drop 4', body: fields('four', 2)})];
  const main = document.querySelector('main');
  main.style.cssText = 'display:block;height:760px';
  window.__rebuildSections = () => main.replaceChildren(U.pagedListDetail({rows, key: row => row.id, selected: 0,
    noun: 'lot', splitKey: 'section-columns-check', slots: false, pageSize: 6, defaultSplit: 22,
    master: v => U.columnList({rows: v.rows, key: row => row.id, selected: v.selected, select: v.select,
      columns: [{key: 'name', label: 'Name'}]}),
    detail: row => U.detailPanel({title: row.name, body: [U.tabbedPanel({label: 'Lot details',
      active: window.__sectionActive,
      tabs: [{id: 'drops', label: 'Drops'}, {id: 'combat', label: 'Combat'}],
      change: id => { window.__sectionActive = id; window.__rebuildSections(); },
      paginate: {unpaged: true}, content: sections()})]})}));
  window.__rebuildSections();
}"""

SECTIONS = """() => [...document.querySelectorAll('main .lex-tweaks-paged .lex-tweak-column')]
  .map(column => [...column.children]
    .map(section => section.querySelector('.lex-detail-section-title-text')?.textContent.trim()))"""

LANES = """() => {
  const out = {};
  for (let index = 0; index < localStorage.length; index++) {
    const key = localStorage.key(index);
    if (!key || !key.includes('.property-layout.')) continue;
    try { Object.assign(out, JSON.parse(localStorage.getItem(key)).lanes || {}); } catch (_error) {}
  }
  return out;
}"""


def build(page):
    page.set_viewport_size({"width": 1700, "height": 800})
    framework(page)
    mount_shell(page, True)
    page.evaluate(BUILD)
    page.wait_for_timeout(400)


def drag_section(page, name, target_name, after):
    source = page.locator(".lex-detail-section-title", has_text=name)
    target = page.locator(".lex-detail-section-title", has_text=target_name)
    section = page.locator(".lex-detail-section", has=target)
    box = section.bounding_box()
    source.drag_to(section, target_position={"x": 10, "y": box["height"] - 4 if after else 2})
    page.wait_for_timeout(250)


def test_section_drop_pins_columns_and_survives_widening(page):
    build(page)
    set_columns(page, 2)
    assert page.evaluate(SECTIONS) == [["Drop 1"], ["Drop 2", "Drop 3", "Drop 4"]]
    drag_section(page, "Drop 2", "Drop 1", after=True)
    assert page.evaluate(SECTIONS) == [["Drop 1", "Drop 2"], ["Drop 3", "Drop 4"]]
    assert page.evaluate(LANES).get("Drop 2") == 0
    page.evaluate("() => window.__rebuildSections()")
    page.wait_for_timeout(400)
    assert page.evaluate(SECTIONS) == [["Drop 1", "Drop 2"], ["Drop 3", "Drop 4"]]
    set_columns(page, 3)
    deal = page.evaluate(SECTIONS)
    assert deal[0] == ["Drop 1", "Drop 2"], deal
    assert deal[2] == [], deal


def test_section_drop_across_columns_moves_reading_order(page):
    build(page)
    set_columns(page, 2)
    drag_section(page, "Drop 4", "Drop 1", after=False)
    assert page.evaluate(SECTIONS) == [["Drop 4", "Drop 1"], ["Drop 2", "Drop 3"]]
    page.evaluate("() => window.__rebuildSections()")
    page.wait_for_timeout(400)
    assert page.evaluate(SECTIONS) == [["Drop 4", "Drop 1"], ["Drop 2", "Drop 3"]]


EMPTY_COLUMN = """() => [...document.querySelectorAll('main .lex-tweaks-paged .lex-tweak-column')]
  .findIndex(column => !column.querySelector('.lex-detail-section,.lex-detail-field'))"""

FIELD_LANE = """() => {
  const field = [...document.querySelectorAll('.lex-detail-field')]
    .find(node => node.textContent.includes('three field 1'));
  const columns = [...document.querySelectorAll('main .lex-tweaks-paged .lex-tweak-column')];
  return columns.indexOf(field.closest('.lex-tweak-column'));
}"""


def test_section_drop_into_an_empty_column_pins_its_lane(page):
    # Lexer: "when I create a new column it's empty... I try to move a
    # header to that blank column... I can't." A page never deals more
    # lanes than cards, so the blank lane comes from pins: Drop 4 joins
    # Drop 1, vacating a lane, and Drop 3's header drops into it. The
    # lane pins, and the arrangement survives a rebuild.
    build(page)
    set_columns(page, 4)
    drag_section(page, "Drop 4", "Drop 1", after=True)
    empty = page.evaluate(EMPTY_COLUMN)
    assert empty >= 0
    page.locator(".lex-detail-section-title", has_text="Drop 3").drag_to(
        page.locator("main .lex-tweaks-paged .lex-tweak-column").nth(empty))
    page.wait_for_timeout(250)
    deal = page.evaluate(SECTIONS)
    assert deal[empty] == ["Drop 3"], deal
    assert page.evaluate(LANES).get("Drop 3") == empty
    page.evaluate("() => window.__rebuildSections()")
    page.wait_for_timeout(400)
    assert page.evaluate(SECTIONS)[empty] == ["Drop 3"]

def test_property_drop_into_an_empty_column_sticks_there(page):
    # The same blank lane takes a property too: it goes loose there and
    # the pin keeps it there across rebuilds.
    build(page)
    set_columns(page, 4)
    drag_section(page, "Drop 4", "Drop 1", after=True)
    empty = page.evaluate(EMPTY_COLUMN)
    assert empty >= 0
    page.locator(".lex-detail-field-label-text", has_text="three field 1").drag_to(
        page.locator("main .lex-tweaks-paged .lex-tweak-column").nth(empty))
    page.wait_for_timeout(250)
    assert page.evaluate(FIELD_LANE) == empty
    lanes = page.evaluate(LANES)
    assert [lane for key, lane in lanes.items()
            if key.startswith("field:") and lane == empty], lanes
    page.evaluate("() => window.__rebuildSections()")
    page.wait_for_timeout(400)
    assert page.evaluate(FIELD_LANE) == empty

def test_stranded_section_rejoins_the_deal_instead_of_vanishing(page):
    # A section the grid holds directly but the dealing dropped (a custom
    # section placed between deals, a re-attached tab shell) used to be
    # destroyed by the deal's replaceChildren, fields and all. It rejoins
    # the dealing instead.
    build(page)
    set_columns(page, 2)
    page.evaluate("""() => {
      const grid = document.querySelector('main .lex-tweak-card-grid');
      const pager = document.querySelector('main .lex-tweaks-paged');
      const stray = [...grid.querySelectorAll('.lex-detail-section')]
        .find(n => n.textContent.includes('Drop 4'));
      grid.append(stray);
      pager.lexRemoveCards(stray);
      pager.lexFitPage();
    }""")
    page.wait_for_timeout(300)
    deal = page.evaluate(SECTIONS)
    assert "Drop 4" in [title for column in deal for title in column], deal
    assert page.locator(".lex-detail-section", has_text="Drop 4").locator(
        ".lex-detail-field").count() == 2
