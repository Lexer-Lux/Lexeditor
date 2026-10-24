"""The label lane stops hogging narrow columns.

The shared name lane grows (via --lex-detail-label-floor) so long names lay
out on at most two lines, capped at half the row. The floor used to only
ever rise: widened for wide columns, it kept hogging after the reader
narrowed past it, and names painted across neighbouring columns. The floor
now follows the cap both ways, and names clamp to two lines with the full
name on hover.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_shared_ui_feedback import framework, page  # noqa: F401,E402
from test_tab_rename import mount_shell  # noqa: E402
from test_detail_field_columns import set_columns  # noqa: E402

NAMES = [
    'Wandering Equipment Identifier Alpha', 'Vagrant Evil Spirit Encounter',
    'Equipment Weight Ratio Limit', 'Maximum Durability Threshold',
    'Ammunition Distance Modifier', 'Critical Hit Damage Bonus',
    'Poise Break Resistance Value', 'Weapon Category Classifier',
]

BUILD = """() => {
  const U = LexeditorUI;
  try { localStorage.clear(); } catch (_error) {}
  const rows = [{id: 0, name: 'Lot 0'}];
  const fields = tag => %s.slice(tag * 2, tag * 2 + 2).map((name, i) => U.detailField({label: name,
    property: 'f' + (tag * 2 + i), control: U.el('input', {type: 'number', value: i})}));
  const sections = [0, 1, 2, 3].map(tag => U.detailSection({title: 'Drop ' + (tag + 1),
    body: fields(tag)}));
  const main = document.querySelector('main');
  main.style.cssText = 'display:block;height:760px';
  main.replaceChildren(U.pagedListDetail({rows, key: row => row.id, selected: 0,
    noun: 'lot', splitKey: 'label-lane-check', slots: false, pageSize: 6, defaultSplit: 22,
    master: v => U.columnList({rows: v.rows, key: row => row.id, selected: v.selected, select: v.select,
      columns: [{key: 'name', label: 'Name'}]}),
    detail: row => U.detailPanel({title: row.name, body: [U.tabbedPanel({label: 'Lot details',
      tabs: [{id: 'drops', label: 'Drops'}],
      paginate: {unpaged: true},
      content: sections})]})}));
}""" % NAMES

STATE = """() => {
  const grid = document.querySelector('main .lex-tweaks-paged .lex-tweak-card-grid');
  const fields = [...document.querySelectorAll('main .lex-detail-field')]
    .filter(field => field.offsetParent);
  const labels = fields.map(field => field.querySelector(':scope > .lex-detail-field-label'));
  const past = labels.filter(label => {
    const box = label.getBoundingClientRect();
    const field = label.parentElement.getBoundingClientRect();
    return box.right > field.right + 1;
  }).length;
  return {
    floor: parseFloat(grid.style.getPropertyValue('--lex-detail-label-floor')) || 0,
    minField: Math.min(...fields.map(field => field.getBoundingClientRect().width)),
    past, labels: labels.length,
  };
}"""


def test_label_floor_follows_column_width_both_ways(page):
    page.set_viewport_size({"width": 1000, "height": 800})
    framework(page)
    mount_shell(page, True)
    page.evaluate(BUILD)
    page.wait_for_timeout(500)
    set_columns(page, 2)
    wide = page.evaluate(STATE)
    assert wide['labels'] == len(NAMES), wide
    assert wide['floor'] > 100, wide
    set_columns(page, 6)
    page.wait_for_timeout(400)
    narrow = page.evaluate(STATE)
    assert narrow['floor'] <= narrow['minField'] / 2 + 1, (wide, narrow)
    assert narrow['past'] == 0, narrow
    set_columns(page, 2)
    page.wait_for_timeout(400)
    back = page.evaluate(STATE)
    assert back['floor'] > narrow['floor'] + 20, (narrow, back)
