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
    assert page.evaluate(COLUMNS) == fitted
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
