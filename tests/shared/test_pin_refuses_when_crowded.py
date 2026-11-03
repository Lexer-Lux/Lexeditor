"""Pinning refuses with a toast when the table has no horizontal room.

Pinning a column into a crowded master table rolls the pin back and says
why, instead of growing the page sideways. A crowded table scrolls inside
its own panel; the body never gains a horizontal scrollbar.
"""
from test_shared_ui_feedback import page, framework

BUILD = '''() => {
  const U = LexeditorUI;
  const root = U.element('div', {class: 'lex-paged-list-detail',
    style: 'display:grid;grid-template-columns:220px 1fr;gap:8px;width:640px'});
  const master = U.element('div', {class: 'lex-barrelled-master', style: 'width:220px'});
  const list = U.element('div', {class: 'lex-column-list'});
  const cells = {};
  for (const key of ['name', 'value', 'extra']) {
    cells[key] = U.element('div', {style: 'width:100px;height:20px'}, key);
  }
  const render = order => {
    list.replaceChildren();
    list.style.setProperty('--lex-column-list-template', order.map(() => 'max-content').join(' '));
    for (const key of order) list.append(cells[key]);
  };
  const prefs = U.columnPreferences('probe-pin-room',
    [{key: 'name', label: 'Name'}, {key: 'value', label: 'Value'},
     {key: 'extra', label: 'Extra', pinned: false}],
    order => render(order.filter(key => key !== 'enabled')));
  render(['name', 'value']);
  master.append(list);
  const detail = U.detailField({label: 'EXTRA', control: U.element('input', {value: 'x'}),
    pin: prefs.pinButton('extra', 'Extra')});
  root.append(master, detail);
  document.querySelector('main').append(root);
  return prefs.isPinned('extra');
}'''

CROWDED = '''() => {
  const U = LexeditorUI;
  const list = U.element('div', {class: 'lex-column-list', style: 'width:200px'});
  list.style.setProperty('--lex-column-list-template',
    Array(10).fill('max-content').join(' '));
  for (let index = 0; index < 10; index++)
    list.append(U.element('div', {style: 'width:150px'}, `c${index}`));
  document.querySelector('main').append(list);
  return {listOverflows: list.scrollWidth > list.clientWidth + 1,
    pageOverflows: document.documentElement.scrollWidth > window.innerWidth + 1};
}'''


def test_pin_refused_with_toast_when_crowded(page):
    framework(page)
    assert page.evaluate(BUILD) is False
    page.locator('.lex-detail-field .lex-column-pin').click()
    toast = page.locator('.lex-toast')
    toast.wait_for(timeout=8000)
    assert 'No room' in (toast.first.inner_text() or '')
    page.wait_for_timeout(500)
    state = page.evaluate('''() => ({
      pinned: document.querySelector('.lex-detail-field .lex-column-pin')
        .classList.contains('pinned'),
      columns: document.querySelector('.lex-column-list').children.length,
    })''')
    assert state == {'pinned': False, 'columns': 2}, state


def test_crowded_table_scrolls_inside_its_panel(page):
    framework(page)
    state = page.evaluate(CROWDED)
    assert state == {'listOverflows': True, 'pageOverflows': False}, state
