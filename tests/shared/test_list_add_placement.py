"""Record creation lives in the detail header, not the list.

A list whose plugin owns creation in its detail header passes
tableAdd:false, and no add button renders in the list at all - not
even the faint hover one, and a plugin-supplied button handed over
with the filters stays where it was put instead of moving to the
corner. Lists still migrating keep the old bottom-right button.
"""
from test_shared_ui_feedback import framework, page  # noqa: F401
from test_tab_rename import mount_shell

BUILD = """(mode) => {
  const U = LexeditorUI;
  const rows = [{id: 0, name: 'Armor 0'}, {id: 1, name: 'Armor 1'}];
  const extra = mode === 'suppressed'
    ? {add: () => {}, tableAdd: false}
    : mode === 'supplied'
      ? {add: () => {}, tableAdd: false, filters: [U.newButton({title: 'Custom add'})]}
      : {add: () => {}};
  const main = document.querySelector('main');
  main.style.cssText = 'display:block;height:760px';
  main.replaceChildren(U.pagedListDetail({rows, key: row => row.id, selected: 0,
    noun: 'armor', pageSize: 6, slots: false,
    master: v => U.columnList({rows: v.rows, key: row => row.id, selected: v.selected,
      select: v.select, columns: [{key: 'name', label: 'Name'}]}),
    detail: row => U.detailPanel({title: row.name, body: []}),
    ...extra}));
}"""


def build(page, mode):
    page.set_viewport_size({"width": 1700, "height": 800})
    framework(page)
    mount_shell(page, True)
    page.evaluate(BUILD, mode)
    page.wait_for_timeout(500)


def test_migrating_lists_keep_the_bottom_right_add_button(page):
    build(page, "default")
    assert page.locator("main .lex-table-add").count() == 1


def test_table_add_false_renders_no_list_button(page):
    build(page, "suppressed")
    assert page.locator("main .lex-table-add").count() == 0


def test_supplied_button_stays_put_when_the_list_add_is_gone(page):
    build(page, "supplied")
    assert page.locator("main .lex-table-add").count() == 0
    assert page.locator("main .lex-new-button").count() == 1
