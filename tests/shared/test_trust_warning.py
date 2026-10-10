"""The first-enable mod warning and the global Trust Warning setting.

Enabling a mod runs its scripts, so the first time any mod is enabled the
reader confirms they trust what they enable. Once accepted the warning never
shows again; the Trust Warning setting (default on) switches it off entirely.
"""
import json
from pathlib import Path

from test_shared_ui_feedback import framework, page  # noqa: F401

from core.settings_manager import SettingsStore

ROOT = Path(__file__).resolve().parents[2]
BASE = json.loads((ROOT / 'ui/default_settings.json').read_text(encoding='utf-8'))

HOST = """(options) => {
  window.calls = [];
  const settings = {...options.settings, defaultValues: {...options.settings}, updateCheckChoices: []};
  const rows = [
    {path: 'C:/lib/game/Mine', folder: 'Mine', name: 'Mine', author: 'Me', description: '', credits: '',
     version: '', missing: [], enabled: false, order: 1, lexmod: null, script: null, error: '', remote: false},
  ];
  const record = name => (...args) => { calls.push([name, args]); };
  window.pywebview = {api: {
    lexeditor_settings: async () => JSON.parse(JSON.stringify(settings)),
    acknowledge_trust_warning: async () => { record('acknowledge_trust_warning')();
      settings.trustWarningSeen = true; return JSON.parse(JSON.stringify(settings)); },
    save_lexeditor_settings: async values => { record('save_lexeditor_settings')(values);
      Object.assign(settings, values); return JSON.parse(JSON.stringify(settings)); },
    save_developer_setting_defaults: async () => JSON.parse(JSON.stringify(settings)),
    mod_library_status: async () => ({canManage: true}),
    onboarding_status: async () => ({show: false, game: 'Test Game'}),
    lexmod_info: async () => ({available: false}),
    mods_overview: async () => ({rows: JSON.parse(JSON.stringify(rows)), canManage: true, remote: [],
      lexmod: {repository: '', url: '', error: ''}}),
    lexmod_update: async () => ({updated: false}),
    set_mod_enabled: async (plugin, path, enabled) => {
      record('set_mod_enabled')(plugin, path, enabled);
      const row = rows.find(item => item.path === path); row.enabled = enabled;
      return JSON.parse(JSON.stringify(row));
    },
  }};
  document.body.insertAdjacentHTML('afterbegin', '<div id="shell"></div>');
  window.shell = LexeditorUI.mountShell({host: '#shell', plugin: {id: 'game', name: 'Test Game'},
    tabs: [{id: 'items', label: 'Items'}],
    activeTab: () => 'items', navigate: () => {}});
}"""


def mount(page, settings):
    framework(page)
    page.evaluate(HOST, {"settings": settings})
    page.locator('[data-tab="mods"]').click()
    page.get_by_role("checkbox", name="Switch Mine").wait_for()


def warned(page):
    return dict(BASE, developerMode=False, developerAuthorized=False,
                developerLogin="", viewPreferences={}, trustWarningSeen=False)


def calls(page, name):
    return [args for call, args in page.evaluate("window.calls") if call == name]


def dialog(page):
    return page.locator(".lex-important-dialog")


def test_trust_warning_defaults_on_and_round_trips(tmp_path):
    store = SettingsStore(tmp_path / 'settings.json', ROOT / 'ui/default_settings.json')
    assert store.snapshot()['trustWarning'] is True
    assert store.snapshot()['trustWarningSeen'] is False
    store.save('daily', trust_warning=False)
    assert store.snapshot()['trustWarning'] is False
    store.save('daily')
    assert store.snapshot()['trustWarning'] is False
    store.save('daily', trust_warning=True)
    assert store.snapshot()['trustWarning'] is True


def test_acknowledge_persists_and_survives_later_saves(tmp_path):
    store = SettingsStore(tmp_path / 'settings.json', ROOT / 'ui/default_settings.json')
    assert store.acknowledge_trust_warning()['trustWarningSeen'] is True
    reopened = SettingsStore(tmp_path / 'settings.json', ROOT / 'ui/default_settings.json')
    assert reopened.snapshot()['trustWarningSeen'] is True
    reopened.save('daily', trust_warning=False)
    assert reopened.snapshot()['trustWarningSeen'] is True


def test_first_enable_warns_and_cancel_keeps_the_mod_off(page):
    mount(page, warned(page))
    page.get_by_role("checkbox", name="Switch Mine").check()
    box = dialog(page)
    box.get_by_role("heading", name="Enable this mod?").wait_for()
    message = box.locator(".lex-important-message").inner_text()
    assert "Are you sure you want to enable this mod? Only enable mods you trust." in message
    assert "shows up the first time you enable a mod" in message
    assert '"Trust Warning"' in message
    box.get_by_role("button", name="Cancel", exact=True).click()
    page.wait_for_timeout(150)
    assert calls(page, "set_mod_enabled") == []
    assert calls(page, "acknowledge_trust_warning") == []
    assert not page.get_by_role("checkbox", name="Switch Mine").is_checked()


def test_confirming_enables_once_and_never_warns_again(page):
    mount(page, warned(page))
    page.get_by_role("checkbox", name="Switch Mine").check()
    dialog(page).get_by_role("button", name="Enable", exact=True).click()
    page.wait_for_function("window.calls.some(c => c[0] === 'set_mod_enabled')")
    assert calls(page, "set_mod_enabled") == [["game", "C:/lib/game/Mine", True]]
    assert len(calls(page, "acknowledge_trust_warning")) == 1
    # Disabling never warns, and the accepted warning never shows again.
    page.get_by_role("checkbox", name="Switch Mine").uncheck()
    page.wait_for_function("window.calls.filter(c => c[0] === 'set_mod_enabled').length === 2")
    assert dialog(page).count() == 0
    page.get_by_role("checkbox", name="Switch Mine").check()
    page.wait_for_function("window.calls.filter(c => c[0] === 'set_mod_enabled').length === 3")
    assert dialog(page).count() == 0
    assert len(calls(page, "acknowledge_trust_warning")) == 1


def test_setting_off_skips_the_warning(page):
    mount(page, {**warned(page), "trustWarning": False})
    page.get_by_role("checkbox", name="Mine enabled").check()
    page.wait_for_function("window.calls.some(c => c[0] === 'set_mod_enabled')")
    assert dialog(page).count() == 0
    assert calls(page, "acknowledge_trust_warning") == []


def test_settings_dialog_offers_trust_warning_on_by_default(page):
    mount(page, warned(page))
    page.evaluate("LexeditorUI.openSettings()")
    box = page.get_by_role("checkbox", name="Trust Warning", exact=True)
    assert box.count() == 1
    assert box.is_checked()
    box.uncheck()
    page.locator(".lex-global-settings .lex-settings-save-control").click()
    page.wait_for_function("window.calls.some(c => c[0] === 'save_lexeditor_settings')")
    assert calls(page, "save_lexeditor_settings")[-1][0]["trustWarning"] is False


def test_mod_dropdown_enable_warns_first(page):
    framework(page)
    page.evaluate("""(settings) => {
      window.changes = [];
      let secondEnabled = false;
      window.pywebview = {api: {
        lexeditor_settings: async () => structuredClone(settings),
        acknowledge_trust_warning: async () => {
          settings.trustWarningSeen = true; return structuredClone(settings); },
      }};
      document.body.insertAdjacentHTML('afterbegin', '<div id="shell"></div>');
      LexeditorUI.mountShell({host: '#shell', plugin: {id: 'fixture', name: 'Fixture'},
        tabs: [], activeTab: () => '', navigate: () => {},
        projectSnapshot: async () => ({canCreate: false, projects: []}),
        sourcesReplaceProjects: true,
        projectSources: () => [{key: 'mine', label: 'First mod', managed: true, enabled: true},
          {key: 'second', label: 'Second mod', managed: true, enabled: secondEnabled, removable: true}],
        changeProjectSource: async (key, change) => { changes.push({key, ...change});
          if (change.enabled !== undefined) secondEnabled = change.enabled; }});
    }""", warned(page))
    page.get_by_role("button", name="Active mod project", exact=True).click()
    page.get_by_role("checkbox", name="Enable Second mod").check()
    dialog(page).get_by_role("heading", name="Enable this mod?").wait_for()
    dialog(page).get_by_role("button", name="Cancel", exact=True).click()
    page.wait_for_timeout(150)
    assert page.evaluate("changes") == []
    page.get_by_role("button", name="Active mod project", exact=True).click()
    page.get_by_role("checkbox", name="Enable Second mod").check()
    dialog(page).get_by_role("button", name="Enable", exact=True).click()
    page.wait_for_function("window.changes.length === 1")
    assert page.evaluate("changes") == [{"key": "second", "enabled": True}]
