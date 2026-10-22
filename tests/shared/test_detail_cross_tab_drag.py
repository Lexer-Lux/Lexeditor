"""Properties drag between a panel's tabs, and both tabs keep their order.

Dropping a property on another tab's button moves it there: the move is
a membership override the caller honors when it rebuilds, so each tab's
own arrangement survives the field leaving or arriving. Undo restores
both the membership and the orders. Tabs the caller did not opt in
(a panel's bespoke tabs) refuse the drop.
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
    {tab: 'Blocking', key: 'ceta', label: 'Ceta'},
    {tab: 'Defense', key: 'gamma', label: 'Gamma'},
    {tab: 'Defense', key: 'delta', label: 'Delta'},
    {tab: 'Defense', key: 'eps', label: 'Eps'}];
  window.drawMock = (active) => {
    const groups = new Map();
    for (const spec of SPECS) {
      if (!groups.has(spec.tab)) groups.set(spec.tab, []);
      groups.get(spec.tab).push(U.detailField({label: spec.label, property: spec.key,
        control: U.el('input', {type: 'number', value: 0})}));
    }
    const tabs = [...groups].map(([title]) => ({id: title.toLowerCase(), label: title}));
    tabs.push({id: 'model', label: 'Model'});
    const shape = U.applyFieldTabOverrides(groups, tabs,
      {accept: ['blocking', 'defense'], callerShape: 'mock'});
    const section = tabs.find(tab => tab.id === (active || 'blocking'));
    const content = section.id === 'model'
      ? [U.detailNote('A bespoke tab.')]
      : groups.get(section.label);
    main.replaceChildren(U.detailPanel({title: 'Mock', body: [U.tabbedPanel(
      {label: 'Mock details', active: section.id, tabs,
        fieldTabs: {shape, accept: ['blocking', 'defense']},
        paginate: {unpaged: true}, change: id => drawMock(id), content})]}));
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


def show(page, name):
    page.locator('.lex-tabbed-panel-tabs .lex-subtab-button',
                 has_text=name).click()
    page.wait_for_timeout(200)


def drag(page, name, target, bottom=False):
    source = page.locator('.lex-detail-field-label-text').filter(has_text=name)
    source.hover()
    box = target.bounding_box()
    source.drag_to(target, target_position={
        'x': 10, 'y': box['height'] - 2 if bottom else 2})
    page.wait_for_timeout(200)


def overrides(page):
    return page.evaluate("""() => {
      const out = {};
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        if (k && k.includes('.fieldtabs.')) out[k] = localStorage.getItem(k);
      }
      return out;
    }""")


def test_field_moves_to_tab_button_and_both_orders_hold(page):
    mount(page)
    drag(page, 'Ceta', page.locator('[data-lex-layout-field="alpha"]'))
    assert order(page) == ['ceta', 'alpha', 'beta']
    show(page, 'Defense')
    drag(page, 'Delta', page.locator('[data-lex-layout-field="gamma"]'))
    assert order(page) == ['delta', 'gamma', 'eps']
    show(page, 'Blocking')
    drag(page, 'Alpha', page.locator(
        '.lex-tabbed-panel-tabs .lex-subtab-button', has_text='Defense'))
    page.wait_for_timeout(400)
    assert order(page) == ['delta', 'gamma', 'eps', 'alpha']
    stored = overrides(page)
    assert len(stored) == 1
    import json
    assert json.loads(next(iter(stored.values()))) == {
        'alpha': {'from': 'blocking', 'to': 'defense'}}
    show(page, 'Blocking')
    page.wait_for_timeout(300)
    assert order(page) == ['ceta', 'beta']


def test_cross_tab_move_undoes(page):
    mount(page)
    drag(page, 'Alpha', page.locator(
        '.lex-tabbed-panel-tabs .lex-subtab-button', has_text='Defense'))
    page.wait_for_timeout(400)
    assert order(page) == ['gamma', 'delta', 'eps', 'alpha']
    page.keyboard.press('Control+z')
    page.wait_for_timeout(400)
    assert order(page) == ['alpha', 'beta', 'ceta']
    show(page, 'Defense')
    page.wait_for_timeout(300)
    assert order(page) == ['gamma', 'delta', 'eps']


def test_undo_after_manual_switch_bounces_back(page):
    mount(page)
    drag(page, 'Alpha', page.locator(
        '.lex-tabbed-panel-tabs .lex-subtab-button', has_text='Defense'))
    page.wait_for_timeout(400)
    assert order(page) == ['gamma', 'delta', 'eps', 'alpha']
    show(page, 'Blocking')
    page.wait_for_timeout(300)
    assert order(page) == ['beta', 'ceta']
    page.keyboard.press('Control+z')
    page.wait_for_timeout(500)
    assert order(page) == ['alpha', 'beta', 'ceta']
    show(page, 'Defense')
    page.wait_for_timeout(300)
    assert order(page) == ['gamma', 'delta', 'eps']


def test_bespoke_tab_refuses_the_drop(page):
    mount(page)
    drag(page, 'Alpha', page.locator(
        '.lex-tabbed-panel-tabs .lex-subtab-button', has_text='Model'))
    page.wait_for_timeout(400)
    assert order(page) == ['alpha', 'beta', 'ceta']
    assert overrides(page) == {}
