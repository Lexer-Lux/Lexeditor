"""Dev-mode Add-section button in detail headers.

In Developer Mode every detail panel heading carries an Add-section
button that appends a new custom header to the current panel tab. It
writes the same custom-section store the hold-right gesture writes,
so double-click rename, drag-in and hold-right removal keep working.
The new header survives a restart inside its recorded tab, and adding
one never drops the panel's existing tabs. On a tabbed panel the new
section lands inside the current tab: the tab bar stays on top and
every field stays rendered.
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


def test_add_section_button_shows_a_section_glyph_not_a_plus(page):
    # It sits among the record actions, where a bare "+" reads as the
    # record add button that lives in the list panel.
    mount(page, developer=True)
    button = page.locator(ADD)
    button.wait_for()
    assert button.locator("svg").count() == 1
    assert "+" not in button.text_content()


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


TABBED_BUILD = """() => {
  const U = LexeditorUI;
  const main = document.querySelector('main');
  main.style.cssText = 'display:block;width:900px;min-height:600px;height:600px';
  const SPECS = [
    {tab: 'Combat', key: 'physAtk', label: 'Physical attack'},
    {tab: 'Combat', key: 'magAtk', label: 'Magic attack'},
    {tab: 'Combat', key: 'fireAtk', label: 'Fire attack'},
    {tab: 'Combat', key: 'thunAtk', label: 'Lightning attack'},
    {tab: 'Combat', key: 'stamAtk', label: 'Stamina attack'},
    {tab: 'Combat', key: 'poiseAtk', label: 'Poise attack'},
    {tab: 'Basics', key: 'weight', label: 'Weight'},
    {tab: 'Basics', key: 'price', label: 'Price'}];
  window.drawMock = (active) => {
    const groups = new Map();
    for (const spec of SPECS) {
      if (!groups.has(spec.tab)) groups.set(spec.tab, []);
      groups.get(spec.tab).push(U.detailField({label: spec.label, property: spec.key,
        control: U.el('input', {type: 'number', value: 0})}));
    }
    const tabs = [...groups].map(([title]) => ({id: title.toLowerCase(), label: title}));
    const shape = U.applyFieldTabOverrides(groups, tabs,
      {accept: ['combat', 'basics'], callerShape: 'mock'});
    const section = tabs.find(tab => tab.id === (active || 'combat'));
    main.replaceChildren(U.detailPanel({title: 'Standard Arrow', body: [U.tabbedPanel(
      {label: 'Item details', active: section.id, tabs,
        fieldTabs: {shape, accept: ['combat', 'basics']},
        paginate: {unpaged: true}, change: id => drawMock(id),
        content: groups.get(section.label)})]}));
  };
  drawMock('combat');
}"""


def mount_tabbed(page):
    framework(page)
    mount_shell(page, developer=True)
    page.evaluate(TABBED_BUILD)
    page.wait_for_timeout(400)


def tabbed_geometry(page):
    return page.evaluate("""() => {
      const panel = document.querySelector('.lex-detail-panel');
      const top = panel.getBoundingClientRect().top;
      const bar = panel.querySelector('.lex-tabbed-panel-tabs');
      const heading = panel.querySelector(':scope > .lex-detail-panel-heading');
      const content = panel.querySelector('.lex-tabbed-panel-content');
      const fields = [...content.querySelectorAll('.lex-detail-field')];
      return {
        barTop: bar.getBoundingClientRect().top - top,
        headingTop: heading.getBoundingClientRect().top - top,
        contentHeight: content.getBoundingClientRect().height,
        labels: fields.map(
          f => f.querySelector('.lex-detail-field-label-text').textContent),
        heights: fields.map(f => f.getBoundingClientRect().height),
      };
    }""")


def tabbed_custom_parents(page):
    return page.evaluate("""() => [...document.querySelectorAll(
      '[data-lex-custom-section="true"]')].map(n => n.parentElement.className)""")


def test_adding_a_section_to_a_tab_keeps_every_field_and_the_bar(page):
    # DS1 Items -> Ammo -> Combat: the section used to land beside the
    # tabbed panel, dropping the bar below the heading and collapsing the
    # tab's content to nothing. It lands inside the tab now instead.
    mount_tabbed(page)
    before = tabbed_geometry(page)
    assert before['barTop'] < before['headingTop']
    assert len(before['labels']) == 6
    page.locator(ADD).click()
    page.locator(".lex-detail-section-title",
                 has_text="New section").wait_for()
    page.wait_for_timeout(300)
    after = tabbed_geometry(page)
    assert after['labels'] == before['labels']
    assert all(height > 0 for height in after['heights']), after
    assert after['contentHeight'] > 100, after
    assert after['barTop'] == before['barTop'], (before, after)
    assert after['headingTop'] == before['headingTop'], (before, after)
    assert tabbed_custom_parents(page) == ['lex-tweaks-scroll']


def test_damaged_tab_layout_heals_on_a_restart(page):
    # A layout stored while the section landed beside the panel (bar below
    # the heading, tab collapsed) recovers on reload: the section rejoins
    # the tab content and every field shows again.
    mount_tabbed(page)
    page.locator(ADD).click()
    page.locator(".lex-detail-section-title",
                 has_text="New section").wait_for()
    keep = {**shipped(page, ".property-layout."),
            **shipped(page, ".section-order")}
    assert len(keep) == 2, keep
    damaged = page.evaluate("""() => {
      const panel = document.querySelector('.lex-detail-panel');
      const body = panel.querySelector(':scope > .lex-detail-panel-body');
      body.append(panel.querySelector('[data-lex-custom-section="true"]'));
      const top = panel.getBoundingClientRect().top;
      const bar = panel.querySelector('.lex-tabbed-panel-tabs').getBoundingClientRect();
      const heading = panel.querySelector(
        ':scope > .lex-detail-panel-heading').getBoundingClientRect();
      const content = panel.querySelector(
        '.lex-tabbed-panel-content').getBoundingClientRect();
      return {barTop: bar.top - top, headingTop: heading.top - top,
              contentHeight: content.height};
    }""")
    assert damaged['barTop'] > damaged['headingTop'], damaged
    assert damaged['contentHeight'] < 100, damaged
    page.evaluate("""entries => {
      const keep = Object.entries(entries);
      localStorage.clear();
      for (const [key, value] of keep) localStorage.setItem(key, value);
      document.querySelector('main').replaceChildren();
    }""", keep)
    page.evaluate("drawMock('combat')")
    page.wait_for_timeout(400)
    after = tabbed_geometry(page)
    assert after['labels'] == ['Physical attack', 'Magic attack', 'Fire attack',
                               'Lightning attack', 'Stamina attack', 'Poise attack']
    assert all(height > 0 for height in after['heights']), after
    assert after['barTop'] < after['headingTop'], after
    assert tabbed_custom_parents(page) == ['lex-tweaks-scroll']


def test_damaged_live_panel_heals_on_the_next_section_add(page):
    # The same recovery without a restart: placing another section pulls a
    # stray one back into the tab content beside it.
    mount_tabbed(page)
    page.locator(ADD).click()
    page.locator(".lex-detail-section-title",
                 has_text="New section").wait_for()
    page.evaluate("""() => {
      const panel = document.querySelector('.lex-detail-panel');
      panel.querySelector(':scope > .lex-detail-panel-body')
        .append(panel.querySelector('[data-lex-custom-section="true"]'));
    }""")
    page.locator(ADD).click()
    page.wait_for_timeout(300)
    assert tabbed_custom_parents(page) == ['lex-tweaks-scroll', 'lex-tweaks-scroll']
    after = tabbed_geometry(page)
    assert after['barTop'] < after['headingTop'], after
    assert len(after['labels']) == 6


def test_fields_missing_from_a_stored_tab_layout_still_show(page):
    # Whatever a stored layout omits (or a schema gains later) renders in
    # place: only a card that actually left the columns leaves the dealing.
    mount_tabbed(page)
    page.locator(ADD).click()
    page.locator(".lex-detail-section-title",
                 has_text="New section").wait_for()
    page.evaluate("""() => {
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (!key || !key.includes('.property-layout.')) continue;
        const layout = JSON.parse(localStorage.getItem(key));
        for (const [name, list] of Object.entries(layout)) {
          if (Array.isArray(list) && name.includes(':')) layout[name] = list.slice(0, 1);
        }
        localStorage.setItem(key, JSON.stringify(layout));
      }
      document.querySelector('main').replaceChildren();
    }""")
    page.evaluate("drawMock('combat')")
    page.wait_for_timeout(400)
    after = tabbed_geometry(page)
    assert len(after['labels']) == 6, after
    assert all(height > 0 for height in after['heights']), after
