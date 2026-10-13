"""Metadata gestures (renaming a property or a section, rewording a help
bubble) are Lexeditor's own shipped text, not the record's data, so a
developer can use them on the game's own read-only Vanilla data. An actual
data edit - typing into a control - still asks to create a mod first.
"""
import pytest

from test_shared_ui_feedback import framework, page


def mount_vanilla_shell(page, developer=True):
    """A shell with no mod: Vanilla is the only, active project source."""
    page.evaluate("""developer => {
      window.savedCalls = [];
      window.pywebview = {api: {
        lexeditor_settings: async () => ({developerMode: developer}),
        mod_library_status: async () => ({canManage: true}),
        save_default_view: async (...args) => {
          window.savedCalls.push(args);
          return {saved: true};
        },
      }};
      document.body.insertAdjacentHTML('afterbegin', '<div id="shell"></div>');
      window.shell = LexeditorUI.mountShell({host: '#shell', brand: 'LEXEDITOR',
        plugin: {id: 'fixture', name: 'Fixture'},
        tabs: [{id: 'items', label: 'Items'}], activeTab: () => 'items', navigate() {},
        readonly: () => true,
        projectSnapshot: async () => ({canCreate: false, projects: []}),
        projectSources: () => [{key: 'vanilla', label: 'Vanilla', readOnly: true}],
        projectActiveSource: () => 'vanilla', sourcesReplaceProjects: true});
    }""", developer)
    page.wait_for_timeout(300)


def mount_vanilla_field(page):
    page.evaluate("""() => {
      document.querySelector('main').replaceChildren(
        LexeditorUI.detailField({label: 'Price',
          help: LexeditorUI.infoHelp('How much the shop charges.'),
          control: LexeditorUI.el('input', {type: 'number', value: 10, disabled: true})}));
    }""")
    page.wait_for_timeout(200)


def test_renaming_a_property_name_works_on_vanilla_without_a_mod_prompt(page):
    framework(page)
    mount_vanilla_shell(page)
    mount_vanilla_field(page)
    name = page.locator(".lex-detail-field-label-text").first
    name.dblclick()
    editor = page.locator(".lex-detail-field-label .lex-label-rename").first
    editor.wait_for(timeout=3000)
    assert page.get_by_role("button", name="Create a mod", exact=True).count() == 0
    editor.fill("Cost")
    editor.press("Enter")
    page.wait_for_timeout(200)
    assert name.text_content() == "Cost"
    saved = page.evaluate("window.savedCalls")
    assert saved == [["fixture", "items", {"fixture-items.field.Price.label": "Cost"}]], saved


def test_rewording_a_help_bubble_works_on_vanilla_without_a_mod_prompt(page):
    framework(page)
    mount_vanilla_shell(page)
    mount_vanilla_field(page)
    marker = page.locator(".lex-info-help").first
    marker.dblclick()
    editor = page.locator(".lex-help-edit")
    editor.wait_for(timeout=3000)
    assert page.get_by_role("button", name="Create a mod", exact=True).count() == 0
    editor.fill("New wording for this bubble.")
    editor.press("Enter")
    page.wait_for_timeout(200)
    saved = page.evaluate("window.savedCalls")
    assert len(saved) == 1, saved
    plugin, tab, preferences = saved[0]
    assert (plugin, tab) == ("fixture", "items")
    (value,) = preferences.values()
    assert value == "New wording for this bubble."


def test_a_real_edit_attempt_on_vanilla_still_offers_to_create_a_mod(page):
    framework(page)
    mount_vanilla_shell(page)
    mount_vanilla_field(page)
    control = page.locator(".lex-detail-field-control input")
    box = control.bounding_box()
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.get_by_role("button", name="Create a mod", exact=True).wait_for()
    page.get_by_role("button", name="Cancel", exact=True).click()
    assert page.evaluate("window.savedCalls") == []


def test_a_reader_who_is_not_the_developer_still_gets_the_mod_prompt(page):
    framework(page)
    mount_vanilla_shell(page, developer=False)
    mount_vanilla_field(page)
    # Clicking the name edits nothing and asks nothing; reaching for the
    # value is what offers a mod.
    name = page.locator(".lex-detail-field-label-text").first
    box = name.bounding_box()
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.wait_for_timeout(200)
    assert page.get_by_role("button", name="Create a mod", exact=True).count() == 0
    value = page.locator(".lex-detail-field-control").first
    box = value.bounding_box()
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.get_by_role("button", name="Create a mod", exact=True).wait_for()
    page.get_by_role("button", name="Cancel", exact=True).click()
    assert page.locator(".lex-label-rename").count() == 0


def mount_section(page):
    page.evaluate("""() => {
      document.querySelector('main').replaceChildren(
        LexeditorUI.detailPanel({title: 'Record', body: [
          LexeditorUI.detailSection({title: 'Combat', body: [
            LexeditorUI.detailField({label: 'Power',
              control: LexeditorUI.el('input', {type: 'number', value: 7})})]})]}));
    }""")
    page.wait_for_timeout(200)


def section_title(page):
    return page.locator(".lex-detail-section-title").first.evaluate("n => n.textContent.trim()")


def test_renaming_a_section_heading_ships_and_persists_across_rerender(page):
    framework(page)
    mount_vanilla_shell(page)
    mount_section(page)
    assert section_title(page) == "Combat"
    page.locator(".lex-detail-section-title-text").first.dblclick()
    field = page.locator(".lex-detail-section-title .lex-label-rename").first
    field.wait_for(timeout=3000)
    field.fill("Damage")
    field.press("Enter")
    page.wait_for_timeout(250)
    assert section_title(page) == "Damage"
    saved = page.evaluate("window.savedCalls")
    assert saved == [["fixture", "items", {"fixture-items.section.Combat.label": "Damage"}]], saved
    # The same heading drawn again - a different record's detail panel -
    # reads the chosen wording, the same rule a renamed property follows.
    mount_section(page)
    assert section_title(page) == "Damage", "the saved section heading did not come back"


def test_renaming_one_copy_of_a_heading_relabels_its_other_column(page):
    """A section dealt across paginated columns repeats its heading."""
    framework(page)
    mount_vanilla_shell(page)
    page.evaluate("""() => {
      const section = () => LexeditorUI.detailSection({title: 'Combat', body: [LexeditorUI.detailNote('x')]});
      document.querySelector('main').replaceChildren(section(), section());
    }""")
    page.locator(".lex-detail-section-title-text").first.dblclick()
    field = page.locator(".lex-label-rename").first
    field.wait_for(timeout=3000)
    field.fill("Damage")
    field.press("Enter")
    page.wait_for_timeout(250)
    assert page.locator(".lex-detail-section-title-text").all_text_contents() == ["Damage", "Damage"]


def test_a_collapsible_sections_heading_is_not_renamed_in_place(page):
    """A collapsible summary already owns its click (open/close)."""
    framework(page)
    mount_vanilla_shell(page)
    page.evaluate("""() => {
      document.querySelector('main').replaceChildren(
        LexeditorUI.detailSection({title: 'Combat', collapsible: true,
          body: [LexeditorUI.detailNote('x')]}));
    }""")
    page.locator(".lex-detail-section-title").first.dblclick()
    page.wait_for_timeout(150)
    assert page.locator(".lex-label-rename").count() == 0
    assert page.evaluate("window.savedCalls") == []
