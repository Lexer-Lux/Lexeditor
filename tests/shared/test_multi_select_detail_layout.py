"""Selecting several records keeps the detail pane laid out.

Lexer, with two DS1 armor pieces Ctrl-selected: a giant name in the middle of
an empty pane. The "N records selected" notice was prepended to the panel
itself, took the heading's grid row, and left the body no height at all.
"""
from test_shared_ui_feedback import page, framework


MOUNT = '''() => {
  const U = LexeditorUI;
  const rows = Array.from({length: 4}, (_, id) => ({id, name: 'Piece ' + id}));
  const view = {page: 0, selected: 0};
  const draw = () => document.querySelector('main').replaceChildren(U.pagedListDetail({rows, key: r => r.id,
    selected: view.selected, page: view.page, pageSize: 10, splitKey: 'multi-layout', slots: false,
    search: {value: '', input() {}},
    change: next => { view.page = next.page; view.selected = next.selected; draw(); },
    sync: next => { view.selected = next.selected; },
    master: v => U.columnList({rows: v.rows, key: r => r.id, selected: v.selected, select: v.select,
      columns: [{key: 'name', label: 'Name'}]}),
    detail: r => U.detailPanel({title: r.name, body: [
      U.detailSection({title: 'Basics', body: [U.detailField({label: 'Weight',
        control: U.el('input', {type: 'number', value: r.id, 'aria-label': 'Weight'})})]})]})}));
  document.querySelector('main').style.height = '600px';
  draw();
}'''


def test_a_multi_selection_keeps_its_heading_on_top_and_its_fields_shown(page):
    framework(page)
    page.evaluate(MOUNT)
    rows = page.locator('.lex-column-list .lex-list-row')
    rows.nth(0).click()
    rows.nth(2).click(modifiers=['Control'])
    page.wait_for_timeout(300)
    notice = page.locator('.lex-multi-edit-notice')
    assert notice.count() == 1 and '2 records selected' in notice.text_content()
    title = page.locator('.lex-detail-panel-title').bounding_box()
    weight = page.get_by_role('spinbutton', name='Weight').or_(page.get_by_role('textbox', name='Weight'))
    assert weight.is_visible(), 'the selected record\'s fields must show'
    box = weight.bounding_box()
    assert title['y'] < notice.bounding_box()['y'] < box['y'], (title, notice.bounding_box(), box)


MOUNT_TABBED = '''() => {
  const U = LexeditorUI;
  const rows = Array.from({length: 4}, (_, id) => ({id, name: 'Piece ' + id}));
  const view = {page: 0, selected: 0};
  const section = (title, label) => U.detailSection({title, body: [U.detailField({label,
    control: U.el('input', {type: 'number', value: 1, 'aria-label': label})})]});
  const draw = () => document.querySelector('main').replaceChildren(U.pagedListDetail({rows, key: r => r.id,
    selected: view.selected, page: view.page, pageSize: 10, splitKey: 'multi-tabbed', slots: false,
    search: {value: '', input() {}},
    change: next => { view.page = next.page; view.selected = next.selected; draw(); },
    sync: next => { view.selected = next.selected; },
    master: v => U.columnList({rows: v.rows, key: r => r.id, selected: v.selected, select: v.select,
      columns: [{key: 'name', label: 'Name'}]}),
    detail: r => U.detailPanel({title: r.name, body: [U.tabbedPanel({tabs: [
      {id: 'alpha', label: 'Alpha'}, {id: 'beta', label: 'Beta'}],
      content: id => section(id === 'beta' ? 'Second' : 'First', id === 'beta' ? 'Speed' : 'Power')})]})}));
  document.querySelector('main').style.height = '600px';
  draw();
}'''


def test_a_tabbed_multi_selection_fills_the_detail_below_the_banner(page):
    """A tabbed detail keeps filling the pane when the notice joins it.

    Lexer, with several DS1 rats shift-selected: the notice sat over a blank
    pane. Every fill rule needs the tabbed panel to be an only child, and the
    notice breaks that, so the panel collapsed and the field fitter measured
    a zero-height box and parked every section on one page.
    """
    framework(page)
    page.evaluate(MOUNT_TABBED)
    rows = page.locator('.lex-column-list .lex-list-row')
    rows.nth(0).click()
    rows.nth(2).click(modifiers=['Control'])
    page.wait_for_timeout(300)
    notice = page.locator('.lex-multi-edit-notice')
    assert notice.count() == 1 and '2 records selected' in notice.text_content()
    tabs = page.locator('.lex-tabbed-panel-tabs')
    assert tabs.is_visible(), 'the tab strip must show below the notice'
    content = page.locator('.lex-tabbed-panel-content').bounding_box()
    assert content['height'] > 300, content
    power = page.get_by_role('spinbutton', name='Power').or_(page.get_by_role('textbox', name='Power'))
    assert power.is_visible(), 'the tabbed fields must show below the notice'
    box = power.bounding_box()
    assert notice.bounding_box()['y'] < tabs.bounding_box()['y'] < box['y'], (
        notice.bounding_box(), tabs.bounding_box(), box)
