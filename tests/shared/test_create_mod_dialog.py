"""The shared Create Mod dialog: naming a mod is the only required step,
and choosing a different location is a separate, explicit action next to
it - not a folder picker forced open on every mod.
"""
from test_shared_ui_feedback import framework, page


def mount_shell(page):
    page.evaluate("""() => {
      window.calls = [];
      window.pywebview = {api: {
        mod_library_status: async () => ({canManage: true}),
        create_mod_project: async (...args) => { calls.push(['create_mod_project', args]); return {}; },
        choose_mod_project_location: async (...args) => {
          calls.push(['choose_mod_project_location', args]);
          return {parent: 'D:/Elsewhere', cancelled: false};
        },
      }};
      document.body.insertAdjacentHTML('afterbegin', '<div id="shell"></div>');
      LexeditorUI.mountShell({host: '#shell', plugin: {id: 'fixture', name: 'Fixture'}, tabs: [],
        activeTab: () => '', navigate() {},
        projectSnapshot: async () => ({canCreate: true, projects: []})});
    }""")
    page.wait_for_timeout(200)
    page.locator(".lex-project-select").click()
    page.get_by_role("menuitem", name="Add a Mod", exact=False).click()


def test_creating_a_mod_needs_only_a_name_by_default(page):
    framework(page)
    mount_shell(page)
    page.get_by_role("heading", name="Create New Mod", exact=True).wait_for()
    assert page.get_by_role("button", name="Create", exact=True).count() == 1
    page.get_by_label("New mod name").fill("My Mod")
    page.get_by_role("button", name="Create", exact=True).click()
    page.wait_for_timeout(200)
    calls = page.evaluate("window.calls")
    assert calls == [["create_mod_project", ["fixture", "My Mod", ""]]], calls


def test_choosing_a_different_location_is_a_separate_explicit_step(page):
    framework(page)
    mount_shell(page)
    page.get_by_role("button", name="Choose a different location…", exact=True).click()
    page.get_by_text("Will be created in: D:/Elsewhere", exact=False).wait_for()
    page.get_by_label("New mod name").fill("My Mod")
    page.get_by_role("button", name="Create", exact=True).click()
    page.wait_for_timeout(200)
    calls = page.evaluate("window.calls")
    assert calls == [
        ["choose_mod_project_location", ["fixture"]],
        ["create_mod_project", ["fixture", "My Mod", "D:/Elsewhere"]],
    ], calls


def test_cancelling_the_dialog_creates_nothing(page):
    framework(page)
    mount_shell(page)
    page.get_by_role("button", name="Cancel", exact=True).click()
    page.wait_for_timeout(150)
    assert page.evaluate("window.calls") == []
