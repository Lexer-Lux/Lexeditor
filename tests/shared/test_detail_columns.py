"""A record's details flow into columns, and the reader can set how many.

DS1's details stayed one column at any width: the column count required each
label's longest word to fit its 7.5% lane, ~1100px per column for words like
"Durability". The fixture's labels are real-length words, not "Alpha 1".
The COLUMNS control mirrors BARRELS on the detail side of the same divider.
"""
from test_shared_ui_feedback import framework, page

BUILD = """() => {
  const U = LexeditorUI;
  try { localStorage.clear(); } catch (_error) {}
  const words = ['Durability', 'Resistance', 'Absorption', 'Thunderbolt', 'Equipment', 'Reinforcement'];
  const section = title => U.detailSection({title, body: words.map(word => U.detailField({
    label: `${word} ${title}`, help: U.infoHelp('Help.'), control: U.el('input', {type: 'number', value: 1})}))});
  const rows = Array.from({length: 6}, (_, id) => ({id, name: 'Armor ' + id}));
  const main = document.querySelector('main');
  main.style.cssText = 'display:block;height:760px';
  main.replaceChildren(U.pagedListDetail({rows, key: row => row.id, selected: 0, noun: 'armor',
    splitKey: 'detail-columns-check', slots: false, pageSize: 6, defaultSplit: 22,
    master: v => U.columnList({rows: v.rows, key: row => row.id, selected: v.selected, select: v.select,
      columns: [{key: 'name', label: 'Name'}]}),
    detail: row => U.detailPanel({title: row.name,
      body: ['Defense', 'Absorption', 'Resistance', 'Upgrades'].map(section)})}));
}"""

COLUMNS = """() => new Set([...document.querySelectorAll('.lex-detail .lex-detail-section-title')]
  .filter(node => node.offsetParent).map(node => Math.round(node.getBoundingClientRect().left))).size"""


def build(page, width):
    page.set_viewport_size({"width": width, "height": 800})
    framework(page)
    page.evaluate(BUILD)
    page.wait_for_timeout(400)


def test_real_length_labels_still_get_several_columns(page):
    build(page, 1700)
    assert page.evaluate(COLUMNS) >= 2


def test_the_columns_control_sets_the_count_and_right_click_fits_again(page):
    build(page, 1700)
    control = page.locator(".lex-list-detail-divider .lex-detail-column-control")
    assert control.count() == 1
    assert page.locator(".lex-list-detail-divider .lex-barrel-control").count() == 2  # beside BARRELS
    page.locator(".lex-list-detail-divider").first.hover()
    fitted = page.evaluate(COLUMNS)
    assert control.locator(".lex-barrel-count").text_content() == str(fitted)
    control.locator(".lex-barrel-decrease").click()
    page.wait_for_timeout(300)
    assert page.evaluate(COLUMNS) == max(1, fitted - 1)
    while control.locator(".lex-barrel-decrease").is_enabled():
        control.locator(".lex-barrel-decrease").click()
        page.wait_for_timeout(150)  # the buttons update a frame after the layout
    page.wait_for_timeout(300)
    assert page.evaluate(COLUMNS) == 1
    assert control.locator(".lex-barrel-decrease").is_disabled()
    control.locator(".lex-barrel-increase").click()
    control.locator(".lex-barrel-increase").click()
    page.wait_for_timeout(300)
    assert page.evaluate(COLUMNS) == 3
    assert control.locator(".lex-barrel-count").text_content() == "3"
    control.click(button="right")
    page.wait_for_timeout(300)
    assert page.evaluate(TABBED_COLUMNS) == fitted
    assert page.locator(".lex-paged-list-detail[data-lex-detail-columns]").count() == 0


def test_the_chosen_count_survives_selecting_another_record(page):
    build(page, 1700)
    control = page.locator(".lex-list-detail-divider .lex-detail-column-control")
    page.locator(".lex-list-detail-divider").first.hover()
    while control.locator(".lex-barrel-decrease").is_enabled():
        control.locator(".lex-barrel-decrease").click()
        page.wait_for_timeout(150)  # the buttons update a frame after the layout
    page.wait_for_timeout(300)
    page.locator(".lex-list-row[data-key='3']").click()
    page.wait_for_timeout(400)
    assert page.evaluate(COLUMNS) == 1

TABBED = """() => {
  const U = LexeditorUI;
  try { localStorage.clear(); } catch (_error) {}
  window.__tabbedActive = window.__tabbedActive || 'alpha';
  const words = ['Durability', 'Resistance', 'Absorption', 'Thunderbolt', 'Equipment', 'Reinforcement'];
  const section = title => U.detailSection({title, body: words.map(word => U.detailField({
    label: `${word} ${title}`, help: U.infoHelp('Help.'), control: U.el('input', {type: 'number', value: 1})}))});
  const rows = Array.from({length: 6}, (_, id) => ({id, name: 'Armor ' + id}));
  const main = document.querySelector('main');
  main.style.cssText = 'display:block;height:760px';
  window.__rebuildTabbed = () => main.replaceChildren(U.pagedListDetail({rows, key: row => row.id, selected: 0,
    noun: 'armor', splitKey: 'tabbed-columns-check', slots: false, pageSize: 6, defaultSplit: 22,
    master: v => U.columnList({rows: v.rows, key: row => row.id, selected: v.selected, select: v.select,
      columns: [{key: 'name', label: 'Name'}]}),
    detail: () => U.tabbedPanel({label: 'Details', active: window.__tabbedActive,
      tabs: [{id: 'alpha', label: 'Alpha'}, {id: 'beta', label: 'Beta'}],
      change: id => { window.__tabbedActive = id; window.__rebuildTabbed(); },
      content: ['Defense', 'Absorption', 'Resistance', 'Upgrades'].map(section)})}));
  window.__rebuildTabbed();
}"""


TABBED_COLUMNS = """() => new Set([...document.querySelectorAll('main .lex-detail-section-title')]
  .filter(node => node.offsetParent).map(node => Math.round(node.getBoundingClientRect().left))).size"""


def build_tabbed(page, width):
    page.set_viewport_size({"width": width, "height": 800})
    framework(page)
    page.evaluate("() => { delete window.__tabbedActive; }")
    page.evaluate(TABBED)
    page.wait_for_timeout(400)


def test_each_panel_tab_keeps_its_own_column_count(page):
    build_tabbed(page, 1700)
    control = page.locator(".lex-list-detail-divider .lex-detail-column-control")
    page.locator(".lex-list-detail-divider").first.hover()
    fitted = page.evaluate(TABBED_COLUMNS)
    assert fitted >= 2
    while control.locator(".lex-barrel-decrease").is_enabled():
        control.locator(".lex-barrel-decrease").click()
        page.wait_for_timeout(150)
    page.wait_for_timeout(300)
    assert page.evaluate(TABBED_COLUMNS) == 1
    assert page.evaluate("() => localStorage.getItem('lexeditor:columns:tabbed-columns-check:alpha')") == "1"
    page.get_by_role("tab", name="Beta").click()
    page.wait_for_timeout(400)
    # Beta was never set: it fits to width instead of inheriting Alpha's 1.
    assert page.evaluate(TABBED_COLUMNS) == fitted
    while control.locator(".lex-barrel-decrease").is_enabled():
        control.locator(".lex-barrel-decrease").click()
        page.wait_for_timeout(150)
    control.locator(".lex-barrel-increase").click()
    page.wait_for_timeout(300)
    assert page.evaluate(TABBED_COLUMNS) == 2
    assert page.evaluate("() => localStorage.getItem('lexeditor:columns:tabbed-columns-check:beta')") == "2"
    page.get_by_role("tab", name="Alpha").click()
    page.wait_for_timeout(400)
    assert page.evaluate(TABBED_COLUMNS) == 1
    # A rebuild (reopen) remembers both tabs' counts.
    page.evaluate("() => window.__rebuildTabbed()")
    page.wait_for_timeout(400)
    assert page.evaluate(TABBED_COLUMNS) == 1
    page.get_by_role("tab", name="Beta").click()
    page.wait_for_timeout(400)
    assert page.evaluate(TABBED_COLUMNS) == 2
