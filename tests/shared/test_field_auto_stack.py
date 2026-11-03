"""Narrow fields stack like stacked ones instead of squeezing sideways.

Below two hundred pixels a column, an inline field lays out label above
control with both full width, the way a stacked field always does. Side by
side that narrow, the lane and the value squeezed each other unreadable.
Boolean rows stay inline: a lone checkbox under its name reads worse.
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
    noun: 'lot', splitKey: 'autostack-check', slots: false, pageSize: 6, defaultSplit: 22,
    master: v => U.columnList({rows: v.rows, key: row => row.id, selected: v.selected, select: v.select,
      columns: [{key: 'name', label: 'Name'}]}),
    detail: row => U.detailPanel({title: row.name, body: [U.tabbedPanel({label: 'Lot details',
      tabs: [{id: 'drops', label: 'Drops'}],
      paginate: {unpaged: true},
      content: sections})]})}));
}""" % NAMES

STATE = """() => {
  const fields = [...document.querySelectorAll('main .lex-detail-field')]
    .filter(field => field.offsetParent);
  return fields.map(field => {
    const label = field.querySelector(':scope > .lex-detail-field-label').getBoundingClientRect();
    const control = field.querySelector(':scope > .lex-detail-field-control').getBoundingClientRect();
    return {
      field: Math.round(field.getBoundingClientRect().width),
      stacked: label.bottom <= control.top + 1,
      inline: label.right <= control.left + 1 && label.top < control.bottom - 1
        && label.bottom > control.top + 1,
    };
  });
}"""


def test_narrow_columns_stack_and_wide_columns_stay_inline(page):
    page.set_viewport_size({"width": 1000, "height": 800})
    framework(page)
    mount_shell(page, True)
    page.evaluate(BUILD)
    page.wait_for_timeout(500)
    set_columns(page, 2)
    wide = page.evaluate(STATE)
    assert len(wide) == len(NAMES), wide
    assert all(field['inline'] for field in wide), wide
    set_columns(page, 6)
    page.wait_for_timeout(400)
    narrow = page.evaluate(STATE)
    assert all(field['field'] < 200 for field in narrow), (wide, narrow)
    assert all(field['stacked'] for field in narrow), (wide, narrow)
