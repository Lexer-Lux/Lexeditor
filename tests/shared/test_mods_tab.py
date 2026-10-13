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
  window.shell = LexeditorUI.mountShell({host: '#shell', plugin: {id: 'game', name: 'Test Game'},
    tabs: [{id: 'items', label: 'Items'}, {id: 'tweaks', label: 'Tweaks'}],
    activeTab: () => 'items', navigate: tab => { navigated.push(tab); document.querySelector('#main').textContent = 'plugin page ' + tab; },
    ...(options.vanilla ? {readonly: () => true, projectActiveSource: () => 'vanilla'} : {}),
    ...(options.save ? {save: async () => { window.saved = true; }, dirtyCount: () => 1} : {})});
  if (options.vanilla) shell.refresh?.();
}"""


def mount(page, first_run=False, lexmod=False, vanilla=False, conflicts=False, alerts=False, bundle=False, save=False):
    framework(page)
    page.evaluate(HOST, {"firstRun": first_run, "lexmod": lexmod, "vanilla": vanilla, "conflicts": conflicts,
                       "alerts": alerts, "bundle": bundle, "save": save})
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
    names = page.locator(".lex-mods-page .lex-column-list").inner_text()
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


def test_mods_reorder_with_alt_arrow_keys(page):
    mount(page)
    page.locator('[data-tab="mods"]').click()
    page.get_by_role("textbox", name="Name").wait_for()
    rows = page.locator(".lex-mods-page .lex-column-list-row")
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
        "document.querySelector('.lex-mods-page .lex-column-list').innerText.indexOf('Combat')"
        " < document.querySelector('.lex-mods-page .lex-column-list').innerText.indexOf('Mine')")
    # At the top, Alt+Up is a no-op; Alt+Down moves back.
    before = len(calls(page, "move_mod"))
    page.locator(".lex-mods-page .lex-column-list-row").filter(has_text="Combat").focus()
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
      const rows = [...document.querySelectorAll('.lex-mods-page .lex-column-list-row')];
      const data = new DataTransfer(); data.setData('application/x-lex-mod', '1');
      rows[2].dispatchEvent(new DragEvent('drop', {bubbles: true, cancelable: true, dataTransfer: data}));
      return window.calls.some(c => c[0] === 'move_mod');
    }""")
    assert ignored is False
    moved = page.evaluate("""() => {
      const rows = [...document.querySelectorAll('.lex-mods-page .lex-column-list-row')];
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
    names = page.locator(".lex-mods-page .lex-column-list").inner_text()
    assert names.index("Combat") < names.index("Mine"), names


def test_a_mods_settings_and_a_downloadable_module(page):
    mount(page)
    page.locator('[data-tab="mods"]').click()
    page.locator(".lex-mods-page .lex-column-list").get_by_text("Combat").click()
    page.get_by_role("spinbutton", name="Amount").wait_for()
    page.locator(".lex-mods-page .lex-column-list").get_by_text("Extra").click()
    page.get_by_role("button", name="Download", exact=True).click()
    page.wait_for_function("window.calls.some(c => c[0] === 'lexmod_download')")
    assert calls(page, "lexmod_download")[-1] == ["game", ["Extra"]]


def test_the_plus_button_offers_create_and_add(page):
    mount(page)
    page.locator('[data-tab="mods"]').click()
    page.get_by_role("button", name="Add a mod").click()
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
    page.locator(".lex-mods-page .lex-column-list").get_by_text("Combat").click()
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
    combat = page.locator(".lex-mods-page .lex-column-list-row", has_text="Combat").locator(".lex-conflict-mark")
    assert combat.count() == 1
    assert (combat.get_attribute("aria-label") or "").startswith("Mod warnings"), combat.get_attribute("aria-label")
    combat.hover()
    page.locator(".lex-help-popover .lex-conflict-list li").first.wait_for()
    popover = page.locator(".lex-help-popover").inner_text()
    assert "overrides Mine" in popover and "changed since the last build" in popover
    mine = page.locator(".lex-mods-page .lex-column-list-row", has_text="Mine").locator(".lex-conflict-mark")
    assert (mine.get_attribute("aria-label") or "").startswith("Conflicts with other mods")
    # The detail pane repeats the alert as its own note.
    page.locator(".lex-mods-page .lex-column-list").get_by_text("Combat").click()
    page.locator(".lex-detail-note", has_text="This mod changed since the last build.").wait_for()


def test_a_bundles_components_are_ordinary_settings_that_save(page):
    mount(page, bundle=True)
    page.locator('[data-tab="mods"]').click()
    page.locator(".lex-mods-page .lex-column-list").get_by_text("Collection").click()
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
