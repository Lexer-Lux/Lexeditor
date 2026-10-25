"""The panel split restores after a narrow window widens again.

A window narrowed past a pane minimum refits the shares to pixels; those
fitted shares used to overwrite the configured split (32/68 narrowed to
44/56), and the widened window never violated a minimum again, so panes
froze narrow with their labels shrunk for the narrow room. The fitted
shares now render without persisting: widening restores the split, the
detail columns and the label floor exactly.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_shared_ui_feedback import framework, page  # noqa: F401,E402
from test_tab_rename import mount_shell  # noqa: E402

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
    noun: 'lot', splitKey: 'split-restore-check', slots: false, pageSize: 6, defaultSplit: 22,
    master: v => U.columnList({rows: v.rows, key: row => row.id, selected: v.selected, select: v.select,
      columns: [{key: 'name', label: 'Name'}]}),
    detail: row => U.detailPanel({title: row.name, body: [U.tabbedPanel({label: 'Lot details',
      tabs: [{id: 'drops', label: 'Drops'}],
      paginate: {unpaged: true},
      content: sections})]})}));
}""" % NAMES

STATE = """() => {
  const layout = document.querySelector('main .lex-panel-layout');
  const grid = document.querySelector('main .lex-tweak-card-grid');
  const panel = document.querySelector('main .lex-detail-panel');
  // Labels fit by the fitter's own measure: nothing paints past its box.
  const bad = [...document.querySelectorAll('main .lex-detail-field-label')]
    .filter(label => label.offsetParent
      && (label.scrollWidth > label.clientWidth + 1
        || label.scrollHeight > label.clientHeight + 1)).length;
  return {
    template: layout.style.getPropertyValue('--lex-panel-layout-template'),
    panelW: Math.round(panel.getBoundingClientRect().width),
    columns: grid ? [...grid.children].filter(
      n => n.classList.contains('lex-tweak-column')).length : 0,
    floor: grid.style.getPropertyValue('--lex-detail-label-floor'),
    bad,
  };
}"""


def test_panel_split_restores_after_narrow_widens(page):
    page.set_viewport_size({"width": 1400, "height": 800})
    framework(page)
    mount_shell(page, True)
    page.evaluate(BUILD)
    page.wait_for_timeout(600)
    wide1 = page.evaluate(STATE)
    page.set_viewport_size({"width": 900, "height": 800})
    page.wait_for_timeout(600)
    narrow = page.evaluate(STATE)
    page.set_viewport_size({"width": 1400, "height": 800})
    page.wait_for_timeout(600)
    wide2 = page.evaluate(STATE)
    assert (narrow['template'], narrow['columns']) != (wide1['template'], wide1['columns'])
    assert wide2['template'] == wide1['template']
    assert abs(wide2['panelW'] - wide1['panelW']) <= 1
    assert wide2['columns'] == wide1['columns']
    assert wide2['bad'] == 0, wide2
