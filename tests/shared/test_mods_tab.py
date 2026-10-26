"""The shared Mods tab and first-run screen, rendered against a fake host.

Every game gets the same Mods tab, leftmost: its mods in a table, the
selected one's details beside it, and Lexer's Mod modules not downloaded yet
greyed at the end. The first-run screen offers Lexer's Mod once per game.
"""
from test_shared_ui_feedback import framework, page

HOST = """(options) => {
  window.calls = [];
  const rows = [
    {path: 'C:/lib/game/Mine', folder: 'Mine', name: 'Mine', author: 'Me', description: 'Mine.', credits: '',
     version: '', missing: [], enabled: true, order: 1, lexmod: null, script: null, error: '', remote: false},
    {path: 'C:/lib/game/Combat', folder: 'Combat', name: 'Combat', author: 'Lexer', description: '', credits: '',
     version: '', missing: [], enabled: false, order: 2, lexmod: {repository: 'Lexer-Lux/X', version: 'v1'},
     script: {schema: {fields: [{key: 'amount', label: 'Amount', type: 'int', default: 1, min: 0, max: 9}]},
              values: {amount: 3}, error: ''}, error: '', remote: false},
  ];
  if (options.errorRow) { rows[0].error = 'The mod folder could not be read.'; rows[0].missing = ['name']; }
  if (options.versions) rows[0].version = '1.2';
  if (options.requires) rows[1].requirements = [
    {id: 'Mine', name: 'Mine', installed: true, enabled: true},
    {id: 'Ghost', name: '', installed: false, enabled: false}];
  if (options.bundle) rows.push(
    {path: 'C:/lib/game/Collection', folder: 'Collection', name: 'Collection', author: 'Me', description: '', credits: '',
     version: '', missing: [], enabled: true, order: 3, lexmod: null, script: null, error: '', remote: false,
     components: {schema: {title: '', help: '', blocker: '', fields: [
       {key: 'combat', label: 'Combat', type: 'bool', default: false},
       {key: 'balance', label: 'Balance', type: 'bool', default: false}]},
       values: {combat: true, balance: false}, error: ''}});
  let download = {state: 'idle'};
  const record = name => (...args) => { calls.push([name, args]); };
  window.pywebview = {api: {
    mod_library_status: async () => ({canManage: true}),
    onboarding_status: async (...args) => { record('onboarding_status')(...args); return {show: options.firstRun, game: 'Test Game'}; },
    lexmod_info: async () => options.lexmod ? {available: true, features: ['Better combat', 'Fully customizable -- pick and choose which modules you want!']} : {available: false},
    finish_onboarding: async (...args) => { record('finish_onboarding')(...args); return {show: false}; },
    open_lexmod: async (...args) => record('open_lexmod')(...args),
    open_home_link: async (...args) => record('open_home_link')(...args),
    activate_enabled_mods: async (...args) => { record('activate_enabled_mods')(...args); return {activated: true}; },
    // The game's loader reports a conflict while both mods are on.
    mods_overview: async () => ({rows: JSON.parse(JSON.stringify(rows)).map(row =>
        options.conflicts && rows.every(item => item.enabled)
          ? {...row, conflicts: [row.name === 'Combat' ? 'Items 100, Sell value: overrides Mine'
              : "Items 100, Sell value: Combat changes this too and loads later, so this mod's change is not used"]}
          : row).map(row => options.alerts && row.folder === 'Combat' && row.enabled
          ? {...row, alerts: ['This mod changed since the last build.']} : row), canManage: true,
      remote: [{folder: 'Extra', name: 'Extra', author: 'Lexer', description: 'More.', enabled: true, remote: true}],
      lexmod: {repository: 'Lexer-Lux/X', url: 'https://github.com/Lexer-Lux/X', error: ''}}),
    lexmod_update: async () => ({updated: false}),
    save_mod_details: async (plugin, path, details) => {
      record('save_mod_details')(plugin, path, details);
      if (!details.name.trim()) throw new Error('A mod needs a name');
      const row = rows.find(item => item.path === path); Object.assign(row, details); return JSON.parse(JSON.stringify(row));
    },
    set_mod_enabled: async (plugin, path, enabled) => {
      record('set_mod_enabled')(plugin, path, enabled);
      const row = rows.find(item => item.path === path); row.enabled = enabled; return JSON.parse(JSON.stringify(row));
    },
    copy_library_mod: async (plugin, path, name) => {
      record('copy_library_mod')(plugin, path, name);
      rows.push({path: path + ' ' + name, folder: name, name, author: '', description: '', credits: '',
        version: '', missing: [], enabled: false, order: rows.length + 1, lexmod: null, script: null, error: '', remote: false});
      return {};
    },
    remove_mod_project: async (plugin, path) => {
      record('remove_mod_project')(plugin, path);
      const at = rows.findIndex(item => item.path === path);
      if (at >= 0) rows.splice(at, 1);
      return {};
    },
    open_mod_folder: async (...args) => { record('open_mod_folder')(...args); return {}; },
    mod_contents: async (...args) => {
      record('mod_contents')(...args);
      return window.__modContents || {changes: [
        {table: 'EquipParamGoods', id: 100, label: 'Fixture Stone', fields: ['Basic price'],
         added: false, removed: false, before: null, after: null},
        {table: 'Item name', id: 100, label: 'Fixture Stone', fields: [],
         added: false, removed: false, before: 'Old Stone', after: 'Fixture Stone'},
      ], files: [
        {relative: 'param/GameParam/GameParam.parambnd.dcx', size: 12, sizeLabel: '12 B', loaded: true},
        {relative: 'mod.json', size: 30, sizeLabel: '30 B', loaded: false},
      ], truncated: false, changesTruncated: false, canDescribe: true, note: ''};
    },
    move_mod: async (plugin, path, delta) => {
      record('move_mod')(plugin, path, delta);
      const at = rows.findIndex(item => item.path === path);
      const to = Math.min(Math.max(at + delta, 0), rows.length - 1);
      rows.splice(to, 0, ...rows.splice(at, 1));
      return JSON.parse(JSON.stringify(rows[to]));
    },
    save_mod_settings: async (plugin, path, values) => { record('save_mod_settings')(plugin, path, values);
      const row = rows.find(item => item.path === path);
      if (row.components) row.components.values = {...values};
      return JSON.parse(JSON.stringify(row)); },
    lexmod_download: async (...args) => { record('lexmod_download')(...args); download = {state: 'running', phase: 'download', done: 1, total: 2};
      setTimeout(() => { download = {state: 'done', installed: ['Extra'], phase: 'install', done: 1, total: 1}; }, 300); return download; },
    lexmod_download_progress: async () => download,
    lexmod_download_cancel: async (...args) => { record('lexmod_download_cancel')(...args); download = {state: 'cancelled'}; return download; },
  }};
  document.body.insertAdjacentHTML('afterbegin', '<div id="shell"></div>');
  window.navigated = [];
  window.__modsOptions = options;
  if (options.projects) window.pywebview.api.mod_projects = async () => ({projects: [
    {path: "C:/lib/game/Mine", name: "Mine", version: "", valid: true, current: true, enabled: true,
     conflicts: ["Items 100, Sell value: Combat changes this too and loads later"]},
    {path: "C:/lib/game/Tweak", name: "Tweak", version: "", valid: false, current: false, enabled: true,
     notEditable: "A tweak mod: it has no game data to edit here. Its settings are in the Tweaks tab.",
     alerts: ["This mod changed since the last build."]},
    {path: "C:/lib/game/Broken", name: "Broken", version: "", valid: false, current: false, enabled: false,
     notEditable: "This mod has no files the editor can open."},
  ]});
  window.shell = LexeditorUI.mountShell({host: '#shell', plugin: {id: 'game', name: 'Test Game'},
    tabs: [{id: 'items', label: 'Items'}, {id: 'tweaks', label: 'Tweaks'}],
    activeTab: () => 'items', navigate: tab => { navigated.push(tab); document.querySelector('#main').textContent = 'plugin page ' + tab; },
    ...(options.vanilla ? {readonly: () => true, projectActiveSource: () => 'vanilla'} : {}),
    ...(options.save ? {save: async () => { window.saved = true; }, dirtyCount: () => 1} : {})});
  if (options.vanilla) shell.refresh?.();
}"""


def mount(page, first_run=False, lexmod=False, vanilla=False, conflicts=False, alerts=False, bundle=False, save=False, projects=False,
          requires=False, versions=False, error_row=False):
    framework(page)
    page.evaluate(HOST, {"firstRun": first_run, "lexmod": lexmod, "vanilla": vanilla, "conflicts": conflicts,
                       "alerts": alerts, "bundle": bundle, "save": save, "projects": projects, "requires": requires,
                       "versions": versions, "errorRow": error_row})
    page.wait_for_timeout(250)


def calls(page, name):
    return [args for call, args in page.evaluate("window.calls") if call == name]


def test_mods_is_the_leftmost_tab_and_looks_like_tweaks(page):
    mount(page)
    tabs = page.locator("[data-tab]").evaluate_all("nodes => nodes.map(n => n.dataset.tab)")
    assert tabs[0] == "mods" and tabs[-1] == "tweaks", tabs
    assert "lex-tweaks-tab" in page.locator('[data-tab="mods"]').get_attribute("class")
    page.locator('[data-tab="items"]').click()
    page.get_by_text("plugin page items").wait_for()


def test_the_table_lists_mods_then_downloadable_modules_and_edits_details(page):
    mount(page)
    page.locator('[data-tab="mods"]').click()
    page.get_by_role("textbox", name="Name").wait_for()
    assert page.locator('[data-tab="mods"]').get_attribute("class").count("active") == 1
    names = page.locator(".lex-mods-page .lex-barrelled-master .lex-column-list").inner_text()
    assert names.index("Mine") < names.index("Combat") < names.index("Extra"), names
    assert page.locator(".lex-mods-remote", has_text="Extra").count() == 1
    page.get_by_role("textbox", name="Author").fill("Someone")
    page.get_by_role("textbox", name="Author").press("Tab")
    page.wait_for_function("window.calls.some(c => c[0] === 'save_mod_details')")
    assert calls(page, "save_mod_details")[-1][2]["author"] == "Someone"
    name = page.get_by_role("textbox", name="Name")
    name.fill("   ")
    name.press("Tab")
    page.get_by_text("A mod needs a name").wait_for()
    page.locator(".lex-dialog").get_by_role("button", name="Close").click()
    assert page.get_by_role("textbox", name="Name").input_value() == "Mine"
    page.get_by_role("checkbox", name="Mine enabled").uncheck()
    page.wait_for_function("window.calls.some(c => c[0] === 'set_mod_enabled')")
    assert calls(page, "set_mod_enabled")[-1][1:] == ["C:/lib/game/Mine", False]


def test_version_gets_its_own_column(page):
    mount(page, versions=True)
    page.locator('[data-tab="mods"]').click()
    page.get_by_role("textbox", name="Name").wait_for()
    heads = page.locator(
        ".lex-mods-page .lex-barrelled-master .lex-column-list-head-cell").all_inner_texts()
    assert any(head.startswith("Version") for head in heads), heads
    table = page.locator(".lex-mods-page .lex-barrelled-master")
    mine = table.locator(".lex-column-list-row", has_text="Mine").locator(
        '.lex-column-list-cell[data-column-key="version"]')
    assert mine.inner_text().strip() == "1.2"
    combat = table.locator(".lex-column-list-row", has_text="Combat").locator(
        '.lex-column-list-cell[data-column-key="version"]')
    assert combat.inner_text().strip() == "—"
    extra = table.locator(".lex-column-list-row", has_text="Extra").locator(
        '.lex-column-list-cell[data-column-key="version"]')
    assert extra.inner_text().strip() == "—"


def test_mods_reorder_with_alt_arrow_keys(page):
    mount(page)
    page.locator('[data-tab="mods"]').click()
    page.get_by_role("textbox", name="Name").wait_for()
    rows = page.locator(".lex-mods-page .lex-barrelled-master .lex-column-list-row")
    assert rows.nth(0).get_attribute("draggable") == "true"
    assert rows.nth(0).get_attribute("tabindex") == "0"
    assert "Alt+Up or Alt+Down" in (rows.nth(0).get_attribute("aria-description") or "")
    # The downloadable module is not in the library and cannot move.
    assert rows.nth(2).get_attribute("draggable") is None
    rows.filter(has_text="Combat").focus()
    page.keyboard.press("Alt+ArrowUp")
    page.wait_for_function("window.calls.some(c => c[0] === 'move_mod')")
    assert calls(page, "move_mod")[-1] == ["game", "C:/lib/game/Combat", -1]
    page.wait_for_function(
        "document.querySelector('.lex-mods-page .lex-barrelled-master .lex-column-list').innerText.indexOf('Combat')"
        " < document.querySelector('.lex-mods-page .lex-barrelled-master .lex-column-list').innerText.indexOf('Mine')")
    # At the top, Alt+Up is a no-op; Alt+Down moves back.
    before = len(calls(page, "move_mod"))
    page.locator(".lex-mods-page .lex-barrelled-master .lex-column-list-row").filter(has_text="Combat").focus()
    page.keyboard.press("Alt+ArrowUp")
    page.wait_for_timeout(200)
    assert len(calls(page, "move_mod")) == before
    page.keyboard.press("Alt+ArrowDown")
    page.wait_for_function(f"window.calls.filter(c => c[0] === 'move_mod').length > {before}")
    assert calls(page, "move_mod")[-1] == ["game", "C:/lib/game/Combat", 1]


def test_mods_reorder_by_dragging_one_row_onto_another(page):
    mount(page)
    page.locator('[data-tab="mods"]').click()
    page.get_by_role("textbox", name="Name").wait_for()
    # A drop onto the downloadable module is ignored: it has no library place.
    ignored = page.evaluate("""() => {
      const rows = [...document.querySelectorAll('.lex-mods-page .lex-barrelled-master .lex-column-list-row')];
      const data = new DataTransfer(); data.setData('application/x-lex-mod', '1');
      rows[2].dispatchEvent(new DragEvent('drop', {bubbles: true, cancelable: true, dataTransfer: data}));
      return window.calls.some(c => c[0] === 'move_mod');
    }""")
    assert ignored is False
    moved = page.evaluate("""() => {
      const rows = [...document.querySelectorAll('.lex-mods-page .lex-barrelled-master .lex-column-list-row')];
      const data = new DataTransfer();
      rows[1].dispatchEvent(new DragEvent('dragstart', {bubbles: true, cancelable: true, dataTransfer: data}));
      rows[0].dispatchEvent(new DragEvent('dragover', {bubbles: true, cancelable: true, dataTransfer: data}));
      const drop = new DragEvent('drop', {bubbles: true, cancelable: true, dataTransfer: data});
      rows[0].dispatchEvent(drop);
      return {carried: data.getData('application/x-lex-mod'), dropped: drop.defaultPrevented};
    }""")
    assert moved == {"carried": "1", "dropped": True}, moved
    page.wait_for_function("window.calls.some(c => c[0] === 'move_mod')")
    assert calls(page, "move_mod")[-1] == ["game", "C:/lib/game/Combat", -1]
    names = page.locator(".lex-mods-page .lex-barrelled-master .lex-column-list").inner_text()
    assert names.index("Combat") < names.index("Mine"), names


def test_dragging_shows_a_drop_line_and_drops_between_rows(page):
    mount(page)
    page.locator('[data-tab="mods"]').click()
    page.get_by_role("textbox", name="Name").wait_for()
    rows = page.locator(".lex-mods-page .lex-barrelled-master .lex-column-list-row")
    # The detail can paint before the list settles, and a second draw can
    # land between a wait and its read; a box read mid-draw is None.
    page.locator(".lex-mods-page .lex-barrelled-master .lex-column-list").get_by_text("Extra").wait_for()
    box = None
    for _ in range(50):
        box = rows.nth(1).bounding_box()
        if box and box["width"] > 0 and box["height"] > 0:
            break
        page.wait_for_timeout(100)
    assert box, "the second mod row never settled"
    top = box["y"] + box["height"] * 0.25
    bottom = box["y"] + box["height"] * 0.75
    line = page.evaluate("""([top, bottom]) => {
      const rows = [...document.querySelectorAll('.lex-mods-page .lex-barrelled-master .lex-column-list-row')];
      const data = new DataTransfer();
      rows[0].dispatchEvent(new DragEvent('dragstart', {bubbles: true, cancelable: true, dataTransfer: data}));
      const over = y => rows[1].dispatchEvent(new DragEvent('dragover',
        {bubbles: true, cancelable: true, dataTransfer: data, clientY: y}));
      over(top);
      const upper = rows[1].className;
      over(bottom);
      const lower = rows[1].className;
      rows[1].dispatchEvent(new DragEvent('dragleave', {bubbles: true, dataTransfer: data}));
      const left = rows[1].className;
      rows[1].dispatchEvent(new DragEvent('drop',
        {bubbles: true, cancelable: true, dataTransfer: data, clientY: bottom}));
      const afterDrop = rows[1].className;
      return {upper, lower, left, afterDrop};
    }""", [top, bottom])
    assert "lex-drop-before" in line["upper"] and "lex-drop-after" not in line["upper"], line
    assert "lex-drop-after" in line["lower"] and "lex-drop-before" not in line["lower"], line
    assert "lex-drop-before" not in line["left"] and "lex-drop-after" not in line["left"], line
    assert "lex-drop-before" not in line["afterDrop"] and "lex-drop-after" not in line["afterDrop"], line
    page.wait_for_function("window.calls.some(c => c[0] === 'move_mod')")
    assert calls(page, "move_mod")[-1] == ["game", "C:/lib/game/Mine", 1]
    # Dropping a row beside itself lands where it started: no call.
    box = page.locator(".lex-mods-page .lex-barrelled-master .lex-column-list-row").nth(0).bounding_box()
    bottom = box["y"] + box["height"] * 0.75
    before = len(calls(page, "move_mod"))
    page.evaluate("""bottom => {
      const rows = [...document.querySelectorAll('.lex-mods-page .lex-barrelled-master .lex-column-list-row')];
      const data = new DataTransfer();
      rows[0].dispatchEvent(new DragEvent('dragstart', {bubbles: true, cancelable: true, dataTransfer: data}));
      rows[0].dispatchEvent(new DragEvent('drop',
        {bubbles: true, cancelable: true, dataTransfer: data, clientY: bottom}));
    }""", bottom)
    page.wait_for_timeout(200)
    assert len(calls(page, "move_mod")) == before


def test_a_mods_settings_and_a_downloadable_module(page):
    mount(page)
    page.locator('[data-tab="mods"]').click()
    page.locator(".lex-mods-page .lex-barrelled-master .lex-column-list").get_by_text("Combat").click()
    page.get_by_role("spinbutton", name="Amount").wait_for()
    page.locator(".lex-mods-page .lex-barrelled-master .lex-column-list").get_by_text("Extra").click()
    page.get_by_role("button", name="Download", exact=True).click()
    page.wait_for_function("window.calls.some(c => c[0] === 'lexmod_download')")
    assert calls(page, "lexmod_download")[-1] == ["game", ["Extra"]]


def test_the_plus_button_offers_create_and_add(page):
    mount(page)
    page.locator('[data-tab="mods"]').click()
    # Creation lives in the detail header: no add button in the list.
    assert page.locator(".lex-mods-page .lex-table-add").count() == 0
    page.locator(".lex-mods-page .lex-detail-panel-actions").get_by_role("button", name="Add a mod").click()
    for label in ("Create a new mod", "Add a folder…", "Add a ZIP…", "Cancel"):
        page.get_by_role("button", name=label, exact=True).wait_for()
    page.get_by_role("button", name="Cancel", exact=True).click()


def test_first_run_offers_lexers_mod_downloads_it_and_walks_through(page):
    mount(page, first_run=True, lexmod=True)
    page.get_by_role("heading", name="Lexer's Mod for Test Game").wait_for()
    page.get_by_text("Better combat").wait_for()
    page.get_by_role("button", name="my mod").click()
    assert calls(page, "open_lexmod") == [["game"]]
    page.get_by_role("button", name="Download", exact=True).click()
    nxt = page.get_by_role("button", name="Next", exact=True)
    assert nxt.is_disabled()
    page.get_by_role("button", name="Back", exact=True).click()
    assert calls(page, "lexmod_download_cancel")
    page.get_by_role("heading", name="Lexer's Mod for Test Game").wait_for()
    page.get_by_role("button", name="Download", exact=True).click()
    page.wait_for_function("!document.querySelector('.lex-first-run .primary').disabled", timeout=5000)
    nxt.click()
    page.get_by_role("heading", name="Lexer's Mod for Test Game is ready to play!").wait_for()
    assert calls(page, "activate_enabled_mods")
    page.get_by_role("button", name="contact me").click()
    assert calls(page, "open_home_link") == [["twitter"]]
    for heading in ("Mods", "Tweaks", "Please enjoy!"):
        page.get_by_role("button", name="Next").or_(page.get_by_role("button", name="Done")).first.click()
        if heading != "Please enjoy!":
            page.get_by_role("heading", name=heading, exact=True).wait_for()
    page.get_by_role("heading", name="Please enjoy!").wait_for()
    page.get_by_role("button", name="Done").click()
    page.wait_for_function("window.calls.some(c => c[0] === 'finish_onboarding')")
    assert page.locator(".lex-first-run").count() == 0


def test_first_run_without_lexers_mod_starts_at_the_mods_tab_step(page):
    mount(page, first_run=True, lexmod=False)
    page.get_by_role("heading", name="Mods", exact=True).wait_for()
    assert page.get_by_text("Download", exact=True).count() == 0


def test_first_run_no_thanks_skips_the_download(page):
    mount(page, first_run=True, lexmod=True)
    page.get_by_role("button", name="No thanks").click()
    page.get_by_role("heading", name="Mods", exact=True).wait_for()
    assert not calls(page, "lexmod_download")


def test_vanilla_still_switches_mods_and_reads_text_boxes(page):
    """Vanilla locks the game's data, not the mod library or reading."""
    mount(page, vanilla=True)
    page.locator('[data-tab="mods"]').click()
    page.get_by_role("checkbox", name="Switch Combat").click()
    page.wait_for_function("window.calls.some(c => c[0] === 'set_mod_enabled')")
    page.locator(".lex-mods-page .lex-barrelled-master .lex-column-list").get_by_text("Combat").click()
    page.get_by_role("spinbutton", name="Amount").fill("4")
    page.get_by_role("spinbutton", name="Amount").press("Tab")
    page.wait_for_function("window.calls.some(c => c[0] === 'save_mod_settings')")
    assert page.get_by_text("Create a mod to edit?").count() == 0
    page.locator('[data-tab="items"]').click()
    page.evaluate("""() => document.querySelector('#main').replaceChildren(
      LexeditorUI.detailField({label: 'NOTES', control: LexeditorUI.el('textarea', {'aria-label': 'Notes'}, 'vanilla text')}),
      LexeditorUI.detailField({label: 'FLAG', control: LexeditorUI.el('input', {type: 'checkbox', 'aria-label': 'Flag'})}))""")
    notes = page.get_by_role("textbox", name="Notes")
    box = notes.bounding_box()
    # Clicking in, selecting and dragging the resize grip only read the box.
    notes.click()
    page.keyboard.press("Control+A")
    page.mouse.move(box["x"] + box["width"] - 3, box["y"] + box["height"] - 3)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] + 60, box["y"] + box["height"] + 40)
    page.mouse.up()
    assert page.get_by_text("Create a mod to edit?").count() == 0
    assert notes.bounding_box()["height"] > box["height"] + 20
    # Typing into it is an edit, and so is clicking a switch.
    notes.press("x")
    page.get_by_text("Create a mod to edit?").wait_for()
    assert notes.input_value() == "vanilla text"
    page.get_by_role("button", name="Cancel").click()
    page.get_by_role("checkbox", name="Flag").click(force=True)
    page.get_by_text("Create a mod to edit?").wait_for()
    assert not page.get_by_role("checkbox", name="Flag").is_checked()


def test_switched_on_mods_that_conflict_show_a_red_mark_with_the_details(page):
    mount(page, conflicts=True)
    page.locator('[data-tab="mods"]').click()
    page.get_by_role("textbox", name="Name").wait_for()
    assert page.locator(".lex-conflict-mark").count() == 0
    page.get_by_role("checkbox", name="Switch Combat").check()
    # Switching one mod re-reads every row: both now carry the mark.
    page.wait_for_function("document.querySelectorAll('.lex-column-list .lex-conflict-mark').length === 2")
    mark = page.locator(".lex-column-list .lex-conflict-mark").first
    assert mark.inner_text() == "!"
    colour = mark.evaluate("n => getComputedStyle(n).backgroundColor")
    assert colour not in ("rgba(0, 0, 0, 0)", "transparent"), colour
    mark.hover()
    page.locator(".lex-help-popover .lex-conflict-list li").first.wait_for()
    assert "Combat changes this too" in page.locator(".lex-help-popover").inner_text()
    page.get_by_role("checkbox", name="Switch Combat").uncheck()
    page.wait_for_function("!document.querySelector('.lex-column-list .lex-conflict-mark')")


LONG = "A long description.\n" * 8


def test_description_is_as_tall_as_its_text_and_stays_so_after_saving(page):
    # It was a textarea fixed at three rows: saving (which happens when the
    # window loses focus) redrew it back to three rows, whatever its text.
    mount(page)
    page.locator('[data-tab="mods"]').click()
    box = page.get_by_role("textbox", name="Description")
    box.wait_for()
    box.fill(LONG)
    grown = box.evaluate("n => [n.clientHeight, n.scrollHeight]")
    assert grown[0] >= grown[1] - 2, grown
    page.get_by_role("textbox", name="Author").focus()   # change -> save -> redraw
    page.wait_for_function("window.calls.some(c => c[0] === 'save_mod_details' && c[1][2].description.length > 100)")
    page.wait_for_timeout(200)
    after = page.get_by_role("textbox", name="Description").evaluate("n => [n.clientHeight, n.scrollHeight]")
    assert after[0] >= after[1] - 2 and after[0] >= grown[0] - 2, (grown, after)


def test_text_dragged_from_one_box_is_not_dropped_into_another(page):
    # Dropping moved the text: the description lost it, the credits gained it,
    # and both saved at once with no undo.
    mount(page)
    page.locator('[data-tab="mods"]').click()
    page.get_by_role("textbox", name="Description").wait_for()
    blocked = page.evaluate("""() => {
      const description = document.querySelector('[aria-label="Description"]');
      const credits = document.querySelector('[aria-label="Credits"]');
      const data = new DataTransfer(); data.setData('text/plain', 'Mine.');
      description.dispatchEvent(new DragEvent('dragstart', {bubbles: true, cancelable: true, dataTransfer: data}));
      const over = new DragEvent('dragover', {bubbles: true, cancelable: true, dataTransfer: data});
      credits.dispatchEvent(over);
      const drop = new DragEvent('drop', {bubbles: true, cancelable: true, dataTransfer: data});
      credits.dispatchEvent(drop);
      description.dispatchEvent(new DragEvent('dragend', {bubbles: true, dataTransfer: data}));
      // Within one box, dragging still behaves as the browser does.
      description.dispatchEvent(new DragEvent('dragstart', {bubbles: true, cancelable: true, dataTransfer: data}));
      const inside = new DragEvent('drop', {bubbles: true, cancelable: true, dataTransfer: data});
      description.dispatchEvent(inside);
      return {overEffect: over.dataTransfer.dropEffect, dropBlocked: drop.defaultPrevented, insideBlocked: inside.defaultPrevented};
    }""")
    assert blocked == {"overEffect": "none", "dropBlocked": True, "insideBlocked": False}, blocked


def test_a_changed_mod_shows_one_mark_listing_every_flag(page):
    mount(page, conflicts=True, alerts=True)
    page.locator('[data-tab="mods"]').click()
    page.get_by_role("textbox", name="Name").wait_for()
    page.get_by_role("checkbox", name="Switch Combat").check()
    page.wait_for_function("document.querySelectorAll('.lex-column-list .lex-conflict-mark').length === 2")
    combat = page.locator(".lex-mods-page .lex-barrelled-master .lex-column-list-row", has_text="Combat").locator(".lex-conflict-mark")
    assert combat.count() == 1
    assert (combat.get_attribute("aria-label") or "").startswith("Mod warnings"), combat.get_attribute("aria-label")
    # A squeezed name column truncates the name text; the mark stays
    # inside its own cell instead of sliding under the next column.
    inside = combat.evaluate("""mark => {
      const cell = mark.closest(".lex-column-list-cell").getBoundingClientRect();
      const box = mark.getBoundingClientRect();
      return cell.x <= box.x && box.right <= cell.right;
    }""")
    assert inside
    combat.hover()
    page.locator(".lex-help-popover .lex-conflict-list li").first.wait_for()
    popover = page.locator(".lex-help-popover").inner_text()
    assert "overrides Mine" in popover and "changed since the last build" in popover
    mine = page.locator(".lex-mods-page .lex-barrelled-master .lex-column-list-row", has_text="Mine").locator(".lex-conflict-mark")
    assert (mine.get_attribute("aria-label") or "").startswith("Conflicts with other mods")
    # The detail header carries the same mark; its hover lists every
    # flag, and nothing stands above the tab bar anymore.
    page.locator(".lex-mods-page .lex-barrelled-master .lex-column-list").get_by_text("Combat").click()
    badge = page.locator(".lex-mods-page .lex-detail-panel-actions .lex-conflict-mark")
    assert badge.count() == 1
    bar = page.locator(".lex-mods-page .lex-tabbed-panel-tabs")
    head = page.locator(".lex-mods-page .lex-detail-panel-heading")
    assert head.bounding_box()["y"] + head.bounding_box()["height"] <= bar.bounding_box()["y"]
    assert page.locator(".lex-mods-page .lex-detail-panel-body > :not(.lex-tabbed-panel)").count() == 0


def test_a_bundles_components_are_ordinary_settings_that_save(page):
    mount(page, bundle=True)
    page.locator('[data-tab="mods"]').click()
    page.locator(".lex-mods-page .lex-barrelled-master .lex-column-list").get_by_text("Collection").click()
    combat = page.get_by_role("checkbox", name="Combat", exact=True)
    combat.wait_for()
    assert combat.is_checked()
    assert not page.get_by_role("checkbox", name="Balance", exact=True).is_checked()
    page.get_by_role("checkbox", name="Balance", exact=True).check()
    page.wait_for_function("window.calls.some(c => c[0] === 'save_mod_settings')")
    assert calls(page, "save_mod_settings")[-1][1:] == ["C:/lib/game/Collection", {"combat": True, "balance": True}]

def test_saving_clears_a_rebuilt_mods_alert_mark(page):
    # The save rebuilds the tweaks, so the host stops reporting the alert;
    # the showing Mods tab re-reads its marks instead of waiting for Play.
    mount(page, alerts=True, save=True)
    page.locator('[data-tab="mods"]').click()
    page.get_by_role("textbox", name="Name").wait_for()
    page.get_by_role("checkbox", name="Switch Combat").check()
    page.wait_for_function("document.querySelectorAll('.lex-column-list .lex-conflict-mark').length === 1")
    page.evaluate("window.__modsOptions.alerts = false")
    page.evaluate("window.shell.refresh()")
    page.locator("#global-save").click()
    page.wait_for_function("window.saved === true")
    page.wait_for_function("!document.querySelector('.lex-column-list .lex-conflict-mark')")


def test_mods_detail_switch_fits_its_header(page):
    # The enable switch is square and never outgrows a short header.
    mount(page)
    page.locator('[data-tab="mods"]').click()
    switch = page.get_by_role("checkbox", name="Mine enabled")
    switch.wait_for()
    heading = page.locator(".lex-mods-page .lex-detail-panel-heading")
    for short in (False, True):
        page.wait_for_function("""() => {
          const box = document.querySelector('.lex-mods-page .lex-detail-panel-actions input[type="checkbox"]');
          const head = document.querySelector(".lex-mods-page .lex-detail-panel-heading");
          return box && head && box.getBoundingClientRect().width > 0 && head.getBoundingClientRect().height > 0;
        }""")
        geometry = page.evaluate("""() => {
          const rect = el => { const b = el.getBoundingClientRect();
            return {x: b.x, y: b.y, width: b.width, height: b.height}; };
          return {box: rect(document.querySelector('.lex-mods-page .lex-detail-panel-actions input[type="checkbox"]')),
            head: rect(document.querySelector(".lex-mods-page .lex-detail-panel-heading")),
            actions: rect(document.querySelector(".lex-mods-page .lex-detail-panel-actions"))};
        }""")
        box, head, actions = geometry["box"], geometry["head"], geometry["actions"]
        assert box["width"] == box["height"] > 0, box
        # Compact and fixed, roomy header or short: the name owns the
        # heading's width, and controls no longer grow with it.
        assert abs(box["height"] - 28) <= 1, (box, head)
        assert box["y"] >= head["y"] - 1 and box["y"] + box["height"] <= head["y"] + head["height"] + 1, (box, head)
        assert box["x"] >= head["x"] and box["x"] + box["width"] <= head["x"] + head["width"], (box, head)
        # A short header keeps the same fixed switch without clipping it.
        page.evaluate("""() => {
          const head = document.querySelector(".lex-mods-page .lex-detail-panel-heading");
          head.style.padding = "0";
          head.querySelector(".lex-detail-panel-title").style.fontSize = "10px";
        }""")
        page.wait_for_timeout(150)


def test_mods_detail_switch_tick_scales_with_its_box(page):
    # The drawn tick keeps the 10:6:2 proportions of the 18px box it was
    # drawn for, roomy or short, instead of sitting tiny in a big switch.
    mount(page)
    page.locator('[data-tab="mods"]').click()
    page.get_by_role("checkbox", name="Mine enabled").wait_for()
    for _ in range(2):
        page.wait_for_function("""() => {
          const box = document.querySelector('.lex-mods-page .lex-detail-panel-actions input[type="checkbox"]');
          return box && box.getBoundingClientRect().width > 0;
        }""")
        geometry = page.evaluate("""() => {
          const box = document.querySelector('.lex-mods-page .lex-detail-panel-actions input[type="checkbox"]');
          const tick = getComputedStyle(box, '::before');
          return {side: box.getBoundingClientRect().width, width: parseFloat(tick.width),
                  height: parseFloat(tick.height), stroke: parseFloat(tick.borderBottomWidth)};
        }""")
        side = geometry["side"]
        assert abs(geometry["width"] / side - 0.55) <= 0.06, geometry
        assert abs(geometry["height"] / side - 0.33) <= 0.06, geometry
        assert abs(geometry["stroke"] / side - 0.11) <= 0.04, geometry
        page.evaluate("""() => {
          const head = document.querySelector(".lex-mods-page .lex-detail-panel-heading");
          head.style.padding = "0";
          head.querySelector(".lex-detail-panel-title").style.fontSize = "10px";
        }""")
        page.wait_for_timeout(150)


def test_dropdown_unavailable_rows_show_lock_and_buttons(page, tmp_path):
    mount(page, projects=True)
    page.locator(".lex-project-select").click()
    menu = page.locator(".lex-project-menu")
    menu.wait_for()
    page.wait_for_function(
        "document.querySelectorAll(\'.lex-project-menu-item\').length >= 3")
    page.wait_for_timeout(300)
    menu.screenshot(path=str(tmp_path / "menu.png"))
    menu.screenshot(path="C:/Users/Lexer/AppData/Local/Temp/lexeditor-dev/menu.png")
    rows = page.locator(".lex-project-menu-item")
    assert rows.count() >= 3
    tweak = rows.filter(has_text="Tweak").first
    assert tweak.locator(".lex-project-source-mode").inner_text() == "\U0001f512"
    assert tweak.locator(".lex-project-folder").count() == 1
    assert tweak.locator(".lex-project-about").count() == 1
    assert tweak.locator(".lex-project-rename").count() == 0
    assert tweak.locator(".lex-conflict-mark").count() == 1
    broken = rows.filter(has_text="Broken").first
    assert broken.locator(".lex-project-folder").count() == 1
    assert broken.locator(".lex-project-about").count() == 1
    mine = rows.filter(has_text="Mine").first
    assert mine.locator(".lex-project-rename").count() == 1
    assert mine.locator(".lex-conflict-mark").count() == 1
    centers = page.evaluate("""() => {
      const lanes = [...document.querySelectorAll('.lex-project-menu-item-actions')];
      return lanes.map(lane => [...lane.children].map(child => {
        const r = child.getBoundingClientRect();
        return Math.round((r.y + r.height / 2) * 10) / 10;
      }));
    }""")
    for lane in centers:
        assert max(lane) - min(lane) <= 1, lane


def test_mods_detail_header_has_add_duplicate_delete_and_open_buttons(page):
    mount(page)
    page.locator('[data-tab="mods"]').click()
    header = page.locator(".lex-mods-page .lex-detail-panel-actions")
    header.get_by_role("checkbox", name="Mine enabled").wait_for()
    buttons = header.get_by_role("button")
    assert [buttons.nth(index).get_attribute("aria-label") for index in range(buttons.count())] == [
        "Add a mod", "Make an editable copy of Mine", "Remove Mine from the library", "Open Mine's folder"]
    assert buttons.nth(0).locator("svg").count() == 1
    assert buttons.nth(1).locator("svg").count() == 1
    assert buttons.nth(2).locator("svg").count() == 1
    assert buttons.nth(3).locator("svg").count() == 1
    assert page.get_by_role("button", name="Open folder", exact=True).count() == 0


def test_mods_detail_duplicate_copies_through_the_naming_dialog(page):
    mount(page)
    page.locator('[data-tab="mods"]').click()
    page.get_by_role("button", name="Make an editable copy of Mine", exact=True).click()
    page.get_by_text("Managed mods update automatically.", exact=False).wait_for()
    page.get_by_role("button", name="Make a copy", exact=True).click()
    page.get_by_label("New mod name").fill("Mine Again")
    page.get_by_role("button", name="Create copy", exact=True).click()
    page.wait_for_function("window.calls.some(c => c[0] === 'copy_library_mod')")
    assert calls(page, "copy_library_mod")[-1][1:] == ["C:/lib/game/Mine", "Mine Again"]


def test_mods_detail_delete_removes_the_library_entry(page):
    mount(page)
    page.locator('[data-tab="mods"]').click()
    page.get_by_role("button", name="Remove Mine from the library", exact=True).click()
    page.get_by_text("Its files stay on disk", exact=False).wait_for()
    page.get_by_role("button", name="Remove", exact=True).click()
    page.wait_for_function("window.calls.some(c => c[0] === 'remove_mod_project')")
    assert calls(page, "remove_mod_project")[-1][1:] == ["C:/lib/game/Mine"]
    page.wait_for_function(
        "document.querySelector('.lex-mods-page .lex-detail-panel-title input')?.value === 'Combat'")


def test_mods_detail_delete_is_disabled_for_managed_mods(page):
    mount(page)
    page.locator('[data-tab="mods"]').click()
    page.locator(".lex-mods-page .lex-barrelled-master .lex-column-list").get_by_text("Combat").click()
    page.get_by_role("checkbox", name="Combat enabled").wait_for()
    delete = page.get_by_role("button", name="This mod updates automatically, so it cannot be removed from here")
    assert delete.is_disabled()


def test_mods_detail_open_button_opens_the_folder(page):
    mount(page)
    page.locator('[data-tab="mods"]').click()
    page.get_by_role("button", name="Open Mine's folder", exact=True).click()
    page.wait_for_function("window.calls.some(c => c[0] === 'open_mod_folder')")
    assert calls(page, "open_mod_folder")[-1][1:] == ["C:/lib/game/Mine"]


STRIP = ".lex-tabbed-panel-tabs .lex-subtab-button"


def _detail_tabs(page):
    page.locator('[data-tab="mods"]').click()
    page.get_by_role("checkbox", name="Mine enabled").wait_for()
    page.wait_for_function("window.calls.some(c => c[0] === 'mod_contents')")
    page.locator(".lex-mods-page .lex-detail-panel " + STRIP).first.wait_for()
    return page.locator(".lex-mods-page .lex-detail-panel")


def test_mods_detail_opens_on_details_without_a_folder_property(page):
    mount(page)
    detail = _detail_tabs(page)
    tabs = detail.locator(STRIP)
    # Panel tabs sort themselves: Details, Files, Records; Details first.
    assert [tabs.nth(i).get_attribute("data-subtab") for i in range(3)] == ["details", "files", "records"]
    assert "DETAILS" in tabs.nth(0).inner_text().upper()
    assert "active" in (tabs.nth(0).get_attribute("class") or "")
    for label in ("Name", "Author", "Description", "Credits"):
        assert detail.get_by_role("textbox", name=label).count() == 1
    source = detail.locator(".lex-detail-section", has_text="SOURCE").inner_text()
    assert "FROM" in source
    assert "FOLDER" not in source


def test_mods_detail_lists_changed_records(page):
    mount(page)
    detail = _detail_tabs(page)
    detail.locator(STRIP, has_text="Records").click()
    table = detail.locator(".lex-mod-contents .lex-column-list")
    table.wait_for()
    rows = table.locator(".lex-column-list-row")
    assert rows.count() == 2
    first = rows.nth(0).inner_text()
    assert "Fixture Stone" in first
    assert "EquipParamGoods 100" in first
    assert "Basic price" in first
    second = rows.nth(1).inner_text()
    assert "Old Stone" in second and "Fixture Stone" in second
    assert detail.get_by_role("searchbox", name="Search changed records").count() == 1
    assert detail.locator(".lex-mod-contents .lex-pager").count() == 1


def test_mods_detail_truncated_records_name_their_total(page):
    mount(page)
    page.evaluate("""() => { window.__modContents = {changes: [
        {table: 'EquipParamGoods', id: 100, label: 'Fixture Stone', fields: ['Basic price'],
         added: false, removed: false, before: null, after: null},
        {table: 'EquipParamGoods', id: 101, label: 'Fixture Key', fields: ['Basic price'],
         added: false, removed: false, before: null, after: null},
      ], files: [], truncated: false, changesTruncated: true, totalChanges: 4752,
      canDescribe: true, note: ''}; }""")
    detail = _detail_tabs(page)
    detail.locator(STRIP, has_text="Records").click()
    detail.locator(".lex-mod-contents .lex-column-list").wait_for()
    assert "Showing the first 2 of 4752 changes." in detail.locator(".lex-mod-contents").inner_text()


def test_mods_detail_lists_files_with_loader_marks(page):
    mount(page)
    detail = _detail_tabs(page)
    detail.locator(STRIP, has_text="Files").click()
    table = detail.locator(".lex-mod-contents .lex-column-list")
    table.wait_for()
    rows = table.locator(".lex-column-list-row")
    assert rows.count() == 2
    assert "lex-mod-file-loaded" in (rows.nth(0).get_attribute("class") or "")
    assert "lex-mod-file-loaded" not in (rows.nth(1).get_attribute("class") or "")
    assert "12 B" in rows.nth(0).inner_text()
    read = table.locator('.lex-column-list-cell[data-column-key="loaded"]')
    assert read.nth(0).locator(".lex-boolean-mark.true").inner_text() == "\u2713"
    assert read.nth(0).locator(".lex-boolean-mark").get_attribute("aria-label") == "Yes"
    assert read.nth(1).locator(".lex-boolean-mark.false").inner_text() == "\u00d7"
    assert read.nth(1).locator(".lex-boolean-mark").get_attribute("aria-label") == "No"
    assert rows.nth(0).get_attribute("data-lex-title") == "The mod loader reads this file when the mod is on"
    assert detail.get_by_role("searchbox", name="Search files").count() == 1


def test_mods_detail_contents_empty_states(page):
    mount(page)
    page.evaluate("window.__modContents = {changes: [], files: [], truncated: false,"
                  " changesTruncated: false, canDescribe: false, note: 'Locate the game.'}")
    detail = _detail_tabs(page)
    detail.locator(STRIP, has_text="Records").click()
    assert "Locate the game." in detail.locator(".lex-mod-contents").inner_text()
    detail.locator(STRIP, has_text="Files").click()
    files = detail.locator(".lex-mod-contents").inner_text()
    assert "This mod has no files." in files
    assert "not known for this game" in files
    page.evaluate("window.__modContents = {changes: [], files: [], truncated: false,"
                  " changesTruncated: false, canDescribe: true, note: ''}")
    page.locator(".lex-mods-page .lex-barrelled-master .lex-column-list").get_by_text("Combat").click()
    page.locator(".lex-mods-page .lex-barrelled-master .lex-column-list").get_by_text("Mine").click()
    page.wait_for_function("window.calls.filter(c => c[0] === 'mod_contents').length >= 3")
    # Truly empty: the Records tab grays out with its reason and the
    # panel falls back to Details. Clicking it changes nothing.
    records = detail.locator(STRIP, has_text="Records")
    page.wait_for_function("document.querySelector('[data-subtab=records]')"
                           ".getAttribute(\"aria-disabled\") === \"true\"")
    assert records.get_attribute("aria-disabled") == "true"
    reason = records.evaluate("node => node.dataset.lexTitle || node.getAttribute('title')")
    assert reason == "This mod changes no rows or text entries.", reason
    assert records.evaluate("node => getComputedStyle(node).cursor") == "not-allowed"
    assert records.locator(".lex-tab-label").evaluate(
        "node => getComputedStyle(node).opacity") == "0.4"
    records.evaluate("node => node.click()")
    selected = detail.locator(STRIP + '[aria-selected="true"]').get_attribute("data-subtab")
    assert selected == "files", selected
    assert "No record changes compared to vanilla." not in detail.inner_text()
    # Fallback: Records showing when emptiness arrives lands on Details.
    page.evaluate("window.__modContents = {changes: [], files: [], truncated: false,"
                  " changesTruncated: false, canDescribe: false, note: 'Locate the game.'}")
    page.locator(".lex-mods-page .lex-barrelled-master .lex-column-list").get_by_text("Combat").click()
    page.locator(".lex-mods-page .lex-barrelled-master .lex-column-list").get_by_text("Mine").click()
    page.wait_for_function("window.calls.filter(c => c[0] === 'mod_contents').length >= 5")
    page.wait_for_function("document.querySelector('[data-subtab=records]')"
                           ".getAttribute(\"aria-disabled\") === null")
    detail.locator(STRIP, has_text="Records").click()
    assert "Locate the game." in detail.locator(".lex-mod-contents").inner_text()
    page.evaluate("window.__modContents = {changes: [], files: [], truncated: false,"
                  " changesTruncated: false, canDescribe: true, note: ''}")
    page.locator(".lex-mods-page .lex-barrelled-master .lex-column-list").get_by_text("Combat").click()
    page.locator(".lex-mods-page .lex-barrelled-master .lex-column-list").get_by_text("Mine").click()
    page.wait_for_function("window.calls.filter(c => c[0] === 'mod_contents').length >= 7")
    page.wait_for_function("document.querySelector('[data-subtab=records]')"
                           ".getAttribute(\"aria-disabled\") === \"true\"")
    selected = detail.locator(STRIP + '[aria-selected="true"]').get_attribute("data-subtab")
    assert selected == "details", selected


def test_mods_detail_contents_truncation(page):
    mount(page)
    page.evaluate("window.__modContents = {changes: [{table: 'T', id: 1, label: 'One', fields: [],"
                  " added: false, removed: true, before: null, after: null}],"
                  " files: [{relative: 'a.bin', size: 1, sizeLabel: '1 B', loaded: false}],"
                  " truncated: true, changesTruncated: true, canDescribe: true, note: ''}")
    detail = _detail_tabs(page)
    detail.locator(STRIP, has_text="Records").click()
    assert "Removed" in detail.locator(".lex-mod-contents .lex-column-list-row").first.inner_text()
    assert "Showing the first 1 changes." in detail.inner_text()
    detail.locator(STRIP, has_text="Files").click()
    assert "Showing the first 1 files." in detail.inner_text()


def test_mods_detail_contents_search_filters_each_table(page):
    mount(page)
    detail = _detail_tabs(page)
    detail.locator(STRIP, has_text="Records").click()
    detail.get_by_role("searchbox", name="Search changed records").fill("Basic price")
    page.wait_for_timeout(300)
    assert detail.locator(".lex-mod-contents .lex-column-list-row").count() == 1
    detail.get_by_role("searchbox", name="Search changed records").fill("zzz-no-such-change")
    page.wait_for_timeout(300)
    assert "match this search" in detail.locator(".lex-mod-contents").inner_text()
    detail.locator(STRIP, has_text="Files").click()
    detail.get_by_role("searchbox", name="Search files").fill("GameParam")
    page.wait_for_timeout(300)
    assert detail.locator(".lex-mod-contents .lex-column-list-row").count() == 1



def test_mods_files_fill_the_tab_and_turn_with_the_wheel(page):
    mount(page)
    page.evaluate(
        "window.__modContents = {changes: [], note: '', truncated: false,"
        " changesTruncated: false, canDescribe: true,"
        " files: Array.from({length: 40}, (_, i) => ({relative: 'file-' + i + '.bin',"
        " size: i, sizeLabel: i + ' B', loaded: i % 2 === 0}))}")
    detail = _detail_tabs(page)
    detail.locator(STRIP, has_text="Files").click()
    rows = detail.locator(".lex-mod-contents .lex-column-list-row")
    rows.first.wait_for()
    page.wait_for_timeout(400)
    first_count = rows.count()
    assert first_count > 1
    # The list owns the tab: its foot meets the pager, the pager meets
    # the tab foot, and no scrollbar shares the pager.
    geometry = detail.locator(".lex-mod-contents").evaluate(
        """node => {
          const list = node.querySelector('.lex-column-list');
          const pager = node.querySelector('.lex-pager');
          const tab = node.closest('.lex-tabbed-panel-content');
          return {
            rows: list.querySelectorAll('.lex-column-list-row').length,
            listToPager: pager.getBoundingClientRect().top
              - list.getBoundingClientRect().bottom,
            pagerToTab: tab.getBoundingClientRect().bottom
              - pager.getBoundingClientRect().bottom,
            scrollable: list.scrollHeight > list.clientHeight + 1,
          };
        }""")
    assert geometry["rows"] == first_count, geometry
    assert geometry["listToPager"] <= 2, geometry
    assert geometry["pagerToTab"] <= 2, geometry
    assert geometry["scrollable"] is False, geometry
    # A taller window fits more rows: the page size follows the tab.
    page.set_viewport_size({"width": 1200, "height": 1100})
    page.wait_for_function(
        f"document.querySelectorAll('.lex-mod-contents .lex-column-list-row').length > {first_count}")
    # The wheel turns pages; past either end it does nothing.
    before = rows.first.inner_text()
    detail.locator(".lex-mod-contents .lex-column-list").hover()
    page.mouse.wheel(0, 240)
    page.wait_for_function(
        "document.querySelector('.lex-mod-contents .lex-column-list-row')"
        f".innerText !== {before!r}")
    page.wait_for_timeout(250)
    page.mouse.wheel(0, -240)
    page.wait_for_function(
        "document.querySelector('.lex-mod-contents .lex-column-list-row')"
        f".innerText === {before!r}")
def test_detail_shows_what_mods_the_mod_requires(page):
    # Lexer: the Details panel under Mods should show what mods that mod
    # requires. Each need names its mod and says whether it is on, off,
    # or not installed; a mod with no needs shows no section.
    mount(page, requires=True)
    page.locator('[data-tab="mods"]').click()
    page.get_by_role("textbox", name="Name").wait_for()
    page.locator(".lex-mods-page .lex-barrelled-master .lex-column-list-row").filter(
        has_text="Combat").click()
    section = page.locator(".lex-mods-page .lex-detail-section", has_text="REQUIRES")
    section.wait_for()
    fields = section.locator(".lex-detail-field")
    assert fields.count() == 2
    assert "Mine" in fields.nth(0).inner_text()
    assert fields.nth(0).locator("input").input_value() == "Switched on"
    assert "Ghost" in fields.nth(1).inner_text()
    assert fields.nth(1).locator("input").input_value() == "Not installed"
    page.locator(".lex-mods-page .lex-barrelled-master .lex-column-list-row").filter(
        has_text="Mine").first.click()
    page.wait_for_timeout(250)
    assert page.locator(".lex-mods-page .lex-detail-section", has_text="REQUIRES").count() == 0


def test_column_hover_glows_detail_property_and_back(page):
    # Lexer: hovering a column glows its property in the detail panel and
    # hovering the property glows the column back, filler rows included.
    mount(page, versions=True)
    page.locator('[data-tab="mods"]').click()
    page.get_by_role("textbox", name="Name").wait_for()
    page.locator(".lex-mods-page .lex-barrelled-master .lex-column-list-row").filter(
        has_text="Mine").first.click()
    page.locator('.lex-mods-page [data-lex-property="version"]').wait_for()
    page.locator('.lex-mods-page .lex-column-list-head-cell[data-column-key="version"]').hover()
    page.wait_for_function(
        "document.querySelector('.lex-mods-page [data-lex-property=\"version\"]')"
        ".classList.contains('lex-column-lit')")
    lit, total = page.evaluate("""() => {
        const cells = document.querySelectorAll(
            '.lex-mods-page .lex-column-list-cell[data-column-key="version"]');
        return [[...cells].filter(cell => cell.classList.contains('lex-column-lit')).length,
                cells.length];
    }""")
    assert total > 0 and lit == total, (lit, total)
    fillers_lit, fillers_total = page.evaluate("""() => {
        const cells = document.querySelectorAll(
            '.lex-mods-page .lex-filler-row .lex-column-list-cell[data-column-key="version"]');
        return [[...cells].filter(cell => cell.classList.contains('lex-column-lit')).length,
                cells.length];
    }""")
    assert fillers_total > 0 and fillers_lit == fillers_total, (fillers_lit, fillers_total)
    page.locator('.lex-mods-page [data-lex-property="version"]').hover()
    page.wait_for_function(
        "document.querySelector('.lex-mods-page .lex-column-list-head-cell[data-column-key=\"version\"]')"
        ".classList.contains('lex-column-lit')")


def test_mod_flags_ride_the_header_badge_and_the_tab_bar_never_moves(page):
    mount(page, conflicts=True, alerts=True)
    page.locator('[data-tab="mods"]').click()
    page.get_by_role("textbox", name="Name").wait_for()
    page.locator(".lex-mods-page .lex-column-list-row", has_text="Combat").click()
    page.wait_for_timeout(300)
    bar = page.locator(".lex-mods-page .lex-tabbed-panel-tabs")
    head = page.locator(".lex-mods-page .lex-detail-panel-heading")
    above = lambda: head.bounding_box()["y"] + head.bounding_box()["height"] <= bar.bounding_box()["y"]
    assert above()
    parked = bar.bounding_box()["y"]
    assert page.locator(".lex-mods-page .lex-detail-panel-actions .lex-conflict-mark").count() == 0
    page.get_by_role("checkbox", name="Combat enabled").check()
    page.wait_for_timeout(500)
    badge = page.locator(".lex-mods-page .lex-detail-panel-actions .lex-conflict-mark")
    assert badge.count() == 1
    assert above()
    assert abs(bar.bounding_box()["y"] - parked) < 0.5
    actions = page.locator(".lex-mods-page .lex-detail-panel-actions")
    assert actions.evaluate("el => el.lastElementChild.getAttribute('aria-label')") == "Combat enabled"
    badge.hover()
    popover = page.locator(".lex-help-popover")
    popover.get_by_text("This mod changed since the last build.").wait_for()
    assert "overrides Mine" in popover.inner_text()
    assert page.locator(".lex-mods-page .lex-detail-panel-body > :not(.lex-tabbed-panel)").count() == 0


def test_mod_error_and_missing_name_stay_visible_below_the_tab_bar(page):
    mount(page, error_row=True)
    page.locator('[data-tab="mods"]').click()
    page.get_by_role("textbox", name="Name").wait_for()
    bar = page.locator(".lex-mods-page .lex-tabbed-panel-tabs")
    head = page.locator(".lex-mods-page .lex-detail-panel-heading")
    assert head.bounding_box()["y"] + head.bounding_box()["height"] <= bar.bounding_box()["y"]
    bottom = bar.bounding_box()["y"] + bar.bounding_box()["height"]
    error = page.get_by_text("The mod folder could not be read.")
    assert error.count() == 1
    assert error.bounding_box()["y"] > bottom
    missing = page.get_by_text("This mod has no name yet. Name it to store it properly.")
    assert missing.count() == 1
    assert missing.bounding_box()["y"] > bottom
    assert page.locator(".lex-mods-page .lex-detail-panel-body > :not(.lex-tabbed-panel)").count() == 0
