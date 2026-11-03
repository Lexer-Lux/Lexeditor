"""Detail tabs ship through the shared view-default transport.

Creating or renaming a detail tab saves the shape's layout with
save_default_view, the same call property layouts, renames and help
rewordings save through. After a restart (storage reseeded from those
shipped defaults alone) the tabs come back with their names.
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


def mount(page):
    framework(page)
    mount_shell(page)
    page.evaluate(BUILD)
    page.wait_for_timeout(400)


def shipped(page):
    """The per-shape detail-tab saves the host received."""
    calls = page.evaluate("window.savedCalls")
    found = {}
    for _plugin, _tab, preferences in calls:
        for key, value in preferences.items():
            if ".detailtabs." in key:
                found[key] = value
    return found


def test_creating_a_detail_tab_ships_the_layout(page):
    mount(page)
    page.locator(".lex-detail-panel-heading").click(button="right")
    page.get_by_role("heading", name="New detail tab").wait_for()
    page.get_by_label("Tab name").fill("Combat")
    page.get_by_role("button", name="Create").click()
    page.locator(".lex-detail-tabs .lex-tabstrip-button", has_text="Combat").wait_for()
    # The column pager hands the panel to the tabs it just gained.
    assert page.locator(".lex-detail-panel > .lex-tweaks-paged .lex-tweaks-pages").count() == 0
    assert page.locator(".lex-detail-tabpane").count() == 1
    saved = shipped(page)
    assert len(saved) == 1, saved
    key, value = next(iter(saved.items()))
    assert key.startswith("fixture-items.detailtabs."), key
    assert '"label":"Combat"' in value.replace(" ", ""), value


def test_renaming_a_detail_tab_ships_and_survives_a_restart(page):
    mount(page)
    page.locator(".lex-detail-panel-heading").click(button="right")
    page.get_by_role("heading", name="New detail tab").wait_for()
    page.get_by_label("Tab name").fill("Combat")
    page.get_by_role("button", name="Create").click()
    page.locator(".lex-detail-tabs .lex-tabstrip-button", has_text="Combat").wait_for()
    page.locator(".lex-detail-tabs .lex-tabstrip-button", has_text="Combat").dblclick()
    page.get_by_role("heading", name="Rename detail tab").wait_for()
    page.get_by_label("Tab name").fill("Fighting")
    page.get_by_role("button", name="Rename", exact=True).click()
    page.locator(".lex-detail-tabs .lex-tabstrip-button", has_text="Fighting").wait_for()
    assert '"label":"Fighting"' in shipped(page)[next(iter(shipped(page)))].replace(" ", "")
    # A restart: storage holds only what the host shipped back.
    page.evaluate("""entries => {
      const keep = Object.entries(entries);
      localStorage.clear();
      for (const [key, value] of keep) localStorage.setItem(key, value);
      document.querySelector('main').replaceChildren();
    }""", shipped(page))
    page.evaluate(BUILD)
    page.wait_for_timeout(400)
    assert page.locator(".lex-detail-tabs .lex-tabstrip-button",
                         has_text="Fighting").count() == 1
    assert page.locator(".lex-detail-tabpane").count() == 1
    titles = page.locator(".lex-detail-tabpane .lex-detail-section-title").all_text_contents()
    assert len(titles) == 3, titles
