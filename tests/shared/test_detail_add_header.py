"""Dev-mode Add-section button in detail headers.

In Developer Mode every detail panel heading carries an Add-section
button that appends a new custom header to the current panel tab. It
writes the same custom-section store the hold-right gesture writes,
so double-click rename, drag-in and hold-right removal keep working.
The new header survives a restart inside its recorded tab, and adding
one never drops the panel's existing tabs.
"""
from test_shared_ui_feedback import framework, page  # noqa: F401  (fixture)
from test_tab_rename import mount_shell

BUILD = """() => {
  const U = LexeditorUI;
  const section = title => U.detailSection({title, body: [1, 2].map(n =>
    U.detailField({label: `${title} ${n}`, control: U.el('input', {type: 'number', value: n})}))});
  const main = document.querySelector('main');
  main.style.cssText = 'display:block;height:600px';
  main.replaceChildren(U.detailPanel({title: 'Record',
    body: ['Alpha', 'Beta', 'Gamma'].map(section)}));
}"""

ADD = ".lex-detail-panel-actions button[aria-label='Add section']"


def mount(page, developer=True):
    framework(page)
    mount_shell(page, developer=developer)
    page.evaluate(BUILD)
    page.wait_for_timeout(400)


def add_tab(page, name):
    page.locator(".lex-detail-panel-heading").click(button="right")
    page.get_by_role("heading", name="New detail tab").wait_for()
    page.get_by_label("Tab name").fill(name)
    page.get_by_role("button", name="Create").click()
    page.locator(".lex-detail-tabs .lex-tabstrip-button", has_text=name).wait_for()


def shipped(page, infix):
    """The saves the host received whose key holds infix."""
    calls = page.evaluate("window.savedCalls")
    found = {}
    for _plugin, _tab, preferences in calls:
        for key, value in preferences.items():
            if infix in key:
                found[key] = value
    return found


def test_add_section_button_shows_in_developer_mode(page):
    mount(page, developer=True)
    button = page.locator(ADD)
    button.wait_for()
    assert button.is_visible()


def test_no_add_section_button_outside_developer_mode(page):
    mount(page, developer=False)
    assert not page.locator(ADD).is_visible()


def test_adding_a_section_lands_in_the_active_tab_and_ships(page):
    mount(page)
    add_tab(page, "Combat")
    page.locator(ADD).click()
    page.locator(".lex-detail-tabpane .lex-detail-section-title",
                 has_text="New section").wait_for()
    assert page.locator(".lex-detail-tabs .lex-tabstrip-button").count() == 1
    assert page.locator(".lex-detail-tabpane").count() == 1
    titles = page.locator(
        ".lex-detail-tabpane .lex-detail-section-title").all_text_contents()
    assert [title.strip() for title in titles] == [
        "Alpha", "Beta", "Gamma", "New section"]
    customs = shipped(page, ".property-layout.")
    assert len(customs) == 1, customs
    sections = next(iter(customs.values()))
    assert '"title":"New section"' in sections, sections
    tabs = shipped(page, ".detailtabs.")
    assert len(tabs) == 1, tabs
    saved = next(iter(tabs.values())).replace(" ", "")
    assert '"label":"Combat"' in saved, saved
    assert "s:custom-" in saved, saved


def test_added_section_survives_a_restart_inside_its_tab(page):
    mount(page)
    add_tab(page, "Combat")
    page.locator(ADD).click()
    page.locator(".lex-detail-tabpane .lex-detail-section-title",
                 has_text="New section").wait_for()
    keep = {**shipped(page, ".property-layout."),
            **shipped(page, ".detailtabs.")}
    assert len(keep) == 2, keep
    page.evaluate("""entries => {
      const keep = Object.entries(entries);
      localStorage.clear();
      for (const [key, value] of keep) localStorage.setItem(key, value);
      document.querySelector('main').replaceChildren();
    }""", keep)
    page.evaluate(BUILD)
    page.wait_for_timeout(400)
    assert page.locator(".lex-detail-tabs .lex-tabstrip-button",
                         has_text="Combat").count() == 1
    titles = page.locator(
        ".lex-detail-tabpane .lex-detail-section-title").all_text_contents()
    assert [title.strip() for title in titles] == [
        "Alpha", "Beta", "Gamma", "New section"]


def test_removed_section_stays_gone_after_a_restart(page):
    mount(page)
    add_tab(page, "Combat")
    page.locator(ADD).click()
    heading = page.locator(".lex-detail-tabpane .lex-detail-section-title",
                            has_text="New section")
    heading.wait_for()
    box = heading.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down(button="right")
    page.wait_for_timeout(900)
    page.mouse.up(button="right")
    page.wait_for_function(
        "document.querySelectorAll('.lex-detail-section-title').length === 3")
    keep = {**shipped(page, ".property-layout."),
            **shipped(page, ".detailtabs.")}
    page.evaluate("""entries => {
      const keep = Object.entries(entries);
      localStorage.clear();
      for (const [key, value] of keep) localStorage.setItem(key, value);
      document.querySelector('main').replaceChildren();
    }""", keep)
    page.evaluate(BUILD)
    page.wait_for_timeout(400)
    titles = page.locator(
        ".lex-detail-tabpane .lex-detail-section-title").all_text_contents()
    assert [title.strip() for title in titles] == ["Alpha", "Beta", "Gamma"]
