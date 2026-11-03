"""Empty panel tabs gray out with a reason, hide away, and revive on drops.

A tab whose members the overrides drained (or that never had any) stays
in the strip grayed with its reason instead of opening a blank panel:
it ignores clicks, the Tab cycler steps over it, and its cross hides it
into a restore counter with undo behind it. Dropping a property on one
revives it, and a remembered tab that went empty under a new record
falls back to the first live tab with matching content. Bespoke tabs
never derive emptiness from membership.
"""
from test_shared_ui_feedback import framework, page  # noqa: F401  (fixture)
from test_tab_rename import mount_shell

BUILD = """() => {
  const U = LexeditorUI;
  const main = document.querySelector('main');
  main.style.cssText = 'display:block;width:450px;min-height:500px;height:500px';
  const SPECS = [
    {tab: 'Blocking', key: 'alpha', label: 'Alpha'},
    {tab: 'Blocking', key: 'beta', label: 'Beta'},
    {tab: 'Defense', key: 'gamma', label: 'Gamma'},
    {tab: 'Defense', key: 'delta', label: 'Delta'}];
  window.drawMock = (active) => {
    const groups = new Map();
    for (const spec of SPECS) {
      if (!groups.has(spec.tab)) groups.set(spec.tab, []);
      groups.get(spec.tab).push(U.detailField({label: spec.label, property: spec.key,
        control: U.el('input', {type: 'number', value: 0})}));
    }
    const tabs = [...groups].map(([title]) => ({id: title.toLowerCase(), label: title}));
    tabs.push({id: 'charms', label: 'Charms'});
    tabs.push({id: 'model', label: 'Model', bespoke: true});
    const accept = ['blocking', 'defense', 'charms'];
    const shape = U.applyFieldTabOverrides(groups, tabs,
      {accept, callerShape: 'empty-tabs-mock'});
    const members = Object.fromEntries([...groups].map(([title, fields]) =>
      [title.toLowerCase(), fields.map(field => field?.dataset?.lexLayoutField).filter(Boolean)]));
    main.replaceChildren(U.detailPanel({title: 'Mock', body: [U.tabbedPanel(
      {label: 'Mock details', active: active || 'blocking', tabs,
        fieldTabs: {shape, accept, members},
        paginate: {unpaged: true}, change: id => drawMock(id),
        content: (resolved, selected) => resolved === 'model'
          ? [U.detailNote('A bespoke tab.')]
          : groups.get(selected?.label)})]}));
  };
  drawMock('blocking');
}"""


def mount(page):
    framework(page)
    mount_shell(page, developer=True)
    page.evaluate(BUILD)
    page.wait_for_timeout(300)


def order(page):
    return page.locator('.lex-detail-field').evaluate_all(
        'ns=>ns.map(n=>n.dataset.lexLayoutField)')


def active(page):
    return page.locator(
        '.lex-tabbed-panel-tabs .lex-subtab-button.active').evaluate(
            'b=>b.dataset.subtab')


def tab(page, name):
    return page.locator(
        '.lex-tabbed-panel-tabs .lex-subtab-button', has_text=name)


def show(page, name):
    tab(page, name).click()
    page.wait_for_timeout(200)


def drag(page, name, target):
    source = page.locator('.lex-detail-field-label-text').filter(has_text=name)
    source.hover()
    box = target.bounding_box()
    source.drag_to(target, target_position={'x': 10, 'y': 2})
    page.wait_for_timeout(200)


def test_empty_tab_grays_with_reason_and_ignores_clicks(page):
    mount(page)
    charms = tab(page, 'Charms')
    assert charms.get_attribute('aria-disabled') == 'true'
    # Native titles are stripped framework-wide into hover tips plus
    # assistive descriptions; the reason rides on both.
    assert charms.get_attribute('data-lex-title') == 'This tab has no properties.'
    assert charms.get_attribute('aria-description') == 'This tab has no properties.'
    assert charms.evaluate('b=>getComputedStyle(b).cursor') == 'not-allowed'
    assert charms.locator('.lex-tab-label').evaluate(
        'l=>getComputedStyle(l).opacity') == '0.4'
    # Focusable for its reason and its remove mark, but inert: the
    # showing tab does not move.
    charms.focus()
    assert page.evaluate('document.activeElement.dataset.subtab') == 'charms'
    # Forced: Playwright will not click what aria-disabled grays, but a
    # real click lands and the handler swallows it.
    charms.click(force=True)
    page.wait_for_timeout(200)
    assert active(page) == 'blocking'
    assert order(page) == ['alpha', 'beta']
    # The bespoke tab beside it never derives emptiness from membership.
    assert tab(page, 'Model').get_attribute('aria-disabled') is None
    show(page, 'Model')
    assert active(page) == 'model'


def test_empty_tab_hides_restores_and_undoes(page):
    mount(page)
    charms = tab(page, 'Charms')
    charms.hover()
    remove = charms.locator('.lex-subtab-remove')
    assert remove.is_visible()
    # Forced: Playwright treats the grayed ancestor as disabling the
    # mark, but a real click is never blocked by aria-disabled.
    remove.click(force=True)
    page.wait_for_timeout(200)
    assert tab(page, 'Charms').count() == 0
    assert page.locator('.lex-subtab-restore').inner_text() == '+1'
    page.keyboard.press('Control+z')
    page.wait_for_timeout(200)
    charms = tab(page, 'Charms')
    assert charms.count() == 1
    assert charms.get_attribute('aria-disabled') == 'true'
    assert page.locator('.lex-subtab-restore').count() == 0
    # Hide again, then come back through the counter's popover.
    charms.hover()
    charms.locator('.lex-subtab-remove').click(force=True)
    page.wait_for_timeout(200)
    page.locator('.lex-subtab-restore').click()
    page.locator('.lex-choice-popover button', has_text='Charms').click()
    page.wait_for_timeout(200)
    charms = tab(page, 'Charms')
    assert charms.count() == 1
    assert charms.get_attribute('aria-disabled') == 'true'


def test_tab_cycler_skips_empty_tabs(page):
    mount(page)
    page.locator('.lex-tabbed-panel-tabs').hover()
    page.wait_for_timeout(100)
    page.keyboard.press('Tab')
    page.wait_for_timeout(200)
    # Blocking steps over the gray Charms between it and Defense.
    assert active(page) == 'defense'
    assert order(page) == ['gamma', 'delta']


def test_drop_onto_empty_tab_revives_it(page):
    mount(page)
    drag(page, 'Alpha', tab(page, 'Charms'))
    page.wait_for_timeout(400)
    charms = tab(page, 'Charms')
    assert active(page) == 'charms'
    assert charms.get_attribute('aria-disabled') is None
    assert charms.locator('.lex-subtab-remove').count() == 0
    assert order(page) == ['alpha']
    show(page, 'Blocking')
    assert order(page) == ['beta']


def test_stale_active_falls_back_with_matching_content(page):
    mount(page)
    drag(page, 'Alpha', tab(page, 'Defense'))
    page.wait_for_timeout(400)
    show(page, 'Blocking')
    drag(page, 'Beta', tab(page, 'Defense'))
    page.wait_for_timeout(400)
    assert tab(page, 'Blocking').get_attribute('aria-disabled') == 'true'
    # A record switch onto the drained remembered tab: the bar falls
    # back to the first live tab and the content follows it, not blank.
    page.evaluate('drawMock("blocking")')
    page.wait_for_timeout(200)
    assert active(page) == 'defense'
    assert order(page) == ['gamma', 'delta', 'alpha', 'beta']
