"""A list whose records the game names renames them in the table and the
heading, by double-click, through one option on the paged list.

Lexer: "Do we need to make some kind of agents.md change or tester or
something so you start actually making everything that should be editable
also editable in the table, including the names column?"
"""
from test_shared_ui_feedback import framework, page

PAGE = """(readonly) => {
  const U = LexeditorUI;
  window.renamed = [];
  window.prompts = 0;
  if (readonly) {
    window.pywebview = {api: {lexeditor_settings: async () => ({}), mod_library_status: async () => ({canManage: true})}};
    document.body.insertAdjacentHTML('afterbegin', '<div id="shell"></div>');
    U.mountShell({host: '#shell', plugin: {id: 'fixture', name: 'Fixture'}, tabs: [{id: 'items', label: 'Items'}],
      activeTab: () => 'items', navigate() {}, readonly: () => true,
      projectSnapshot: async () => ({canCreate: false, projects: []}),
      projectSources: () => [{key: 'vanilla', label: 'Vanilla', readOnly: true}],
      projectActiveSource: () => 'vanilla', sourcesReplaceProjects: true});
  }
  const rows = [{id: 1, name: 'Dagger'}, {id: 2, name: 'Rat'}];
  window.state = {selected: 1};
  const render = () => document.querySelector('main').replaceChildren(U.pagedListDetail({
    rows, key: row => row.id, selected: state.selected, slots: false, noun: 'records', change: () => render(),
    rename: (row, name) => { renamed.push([row.id, name]); row.name = name; render(); },
    renamable: row => row.id !== 2,
    master: ({rows: listed, selected, select}) => U.columnList({rows: listed, key: row => row.id, selected,
      select: row => { state.selected = row.id; select(row); render(); },
      columns: [{key: 'id', label: 'ID'}, {key: 'name', label: 'Name'}]}),
    detail: row => U.detailPanel({title: row.name, body: []}),
  }));
  render();
}"""


def name_cell(page, text):
    return page.locator('.lex-column-list [data-column-key="name"]', has_text=text)


def test_the_name_cell_renames_the_record(page):
    framework(page)
    page.evaluate(PAGE, False)
    name_cell(page, "Dagger").dblclick()
    editor = page.locator('.lex-cell-editing input')
    editor.fill("Kris")
    editor.press("Enter")
    page.wait_for_timeout(100)
    assert page.evaluate("renamed") == [[1, "Kris"]]
    assert name_cell(page, "Kris").count() == 1


def test_the_heading_renames_the_record(page):
    framework(page)
    page.evaluate(PAGE, False)
    page.locator(".lex-detail-panel-name").dblclick()
    editor = page.locator(".lex-detail-panel-title .lex-label-rename")
    editor.fill("Stiletto")
    editor.press("Enter")
    page.wait_for_timeout(100)
    assert page.evaluate("renamed") == [[1, "Stiletto"]]


def test_a_record_the_game_does_not_name_keeps_a_plain_cell(page):
    framework(page)
    page.evaluate(PAGE, False)
    rat = name_cell(page, "Rat")
    assert "lex-cell-editable" not in rat.get_attribute("class")
    rat.dblclick()
    assert page.locator('.lex-cell-editing').count() == 0


def test_renaming_on_vanilla_offers_a_mod(page):
    framework(page)
    page.evaluate(PAGE, True)
    page.wait_for_timeout(300)
    name_cell(page, "Dagger").dblclick()
    page.get_by_role("button", name="Create a mod", exact=True).wait_for()
    assert page.evaluate("renamed") == []
