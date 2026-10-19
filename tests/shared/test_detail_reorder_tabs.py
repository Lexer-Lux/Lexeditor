"""Reordered properties survive panel-tab switches and refits.

A developer drags Blocking fields into place, opens another panel
tab, and comes back: the order must hold. Panel tabs rebuild their
content on every switch, so the stored property layout has to
re-apply to the rebuilt tab. A refit (resize, zoom, divider drag)
must also keep the live arrangement: the pager deals cards in its
own list order, so field moves re-sequence that list the way
section moves already do. Bare fields, like the monster detail tabs.
"""
from test_shared_ui_feedback import framework, page  # noqa: F401  (fixture)
from test_tab_rename import mount_shell

BUILD = """() => {
  const U = LexeditorUI;
  const main = document.querySelector('main');
  main.style.cssText = 'display:block;width:900px;min-height:500px';
  const field = label => U.detailField({label, property: label.toLowerCase(),
    control: U.el('input', {type: 'number', value: 0})});
  window.drawDetail = (tab) => {
    main.replaceChildren(U.detailPanel({title: 'Record', body: [
      U.tabbedPanel({label: 'Monster details', active: tab,
        tabs: [{id: 'blocking', label: 'Blocking'},
               {id: 'defense', label: 'Defense'}],
        paginate: {unpaged: true}, change: id => drawDetail(id),
        content: (tab === 'blocking'
          ? ['Alpha', 'Beta', 'Gamma', 'Delta', 'Epsilon', 'Zeta']
          : ['Armor', 'Poise']).map(field)})]}));
  };
  drawDetail('blocking');
}"""


def mount(page):
    framework(page)
    mount_shell(page, developer=True)
    page.evaluate(BUILD)
    page.wait_for_timeout(300)


PAGED_BUILD = """() => {
  const U = LexeditorUI;
  const main = document.querySelector('main');
  main.style.cssText = 'display:block;width:900px;min-height:600px';
  const field = label => U.detailField({label, property: label.toLowerCase(),
    control: U.el('input', {type: 'number', value: 0})});
  window.drawPaged = () => {
    main.replaceChildren(U.detailPanel({title: 'Record', paginate: {},
      body: ['Alpha', 'Beta', 'Gamma', 'Delta', 'Epsilon', 'Zeta'].map(field)}));
  };
  drawPaged();
}"""


def columns(page):
    return page.locator('.lex-tweak-column').count()


def order(page):
    return page.locator('.lex-detail-field').evaluate_all(
        'ns=>ns.map(n=>n.dataset.lexLayoutField)')


def drag(page, name, target, bottom=False):
    source = page.locator('.lex-detail-field-label-text').filter(has_text=name)
    source.hover()
    source.drag_to(target, target_position={
        'x': 10, 'y': target.bounding_box()['height'] - 2 if bottom else 2})
    page.wait_for_timeout(150)


def show(page, name):
    page.locator('.lex-tabbed-panel-tabs .lex-subtab-button',
                 has_text=name).click()


def test_reorder_survives_panel_tab_switches(page):
    mount(page)
    drag(page, 'Zeta', page.locator('[data-lex-layout-field="alpha"]'))
    assert order(page) == ['zeta', 'alpha', 'beta', 'gamma', 'delta', 'epsilon']
    show(page, 'Defense')
    page.locator('.lex-detail-field-label-text',
                 has_text='Armor').wait_for()
    assert order(page) == ['armor', 'poise']
    show(page, 'Blocking')
    page.locator('.lex-detail-field-label-text',
                 has_text='Zeta').wait_for()
    page.wait_for_timeout(300)
    assert order(page) == ['zeta', 'alpha', 'beta', 'gamma', 'delta', 'epsilon']


def test_reorder_survives_a_refit(page):
    mount(page)
    drag(page, 'Zeta', page.locator('[data-lex-layout-field="alpha"]'))
    assert order(page) == ['zeta', 'alpha', 'beta', 'gamma', 'delta', 'epsilon']
    page.set_viewport_size({'width': 650, 'height': 800})
    page.wait_for_timeout(500)
    assert order(page) == ['zeta', 'alpha', 'beta', 'gamma', 'delta', 'epsilon']


def test_reorder_after_a_refit_survives_a_switch(page):
    mount(page)
    drag(page, 'Zeta', page.locator('[data-lex-layout-field="alpha"]'))
    page.set_viewport_size({'width': 650, 'height': 800})
    page.wait_for_timeout(500)
    drag(page, 'Epsilon', page.locator('[data-lex-layout-field="zeta"]'))
    assert order(page) == ['epsilon', 'zeta', 'alpha', 'beta', 'gamma', 'delta']
    show(page, 'Defense')
    page.locator('.lex-detail-field-label-text',
                 has_text='Armor').wait_for()
    show(page, 'Blocking')
    page.locator('.lex-detail-field-label-text',
                 has_text='Epsilon').wait_for()
    page.wait_for_timeout(300)
    assert order(page) == ['epsilon', 'zeta', 'alpha', 'beta', 'gamma', 'delta']


def test_reorder_survives_rebuild_with_different_dealing(page):
    framework(page)
    mount_shell(page, developer=True)
    page.evaluate(PAGED_BUILD)
    page.wait_for_timeout(500)
    assert columns(page) == 2
    drag(page, 'Zeta', page.locator('[data-lex-layout-field="alpha"]'))
    assert order(page) == ['zeta', 'alpha', 'beta', 'gamma', 'delta', 'epsilon']
    page.evaluate("document.querySelector('main').style.width = '380px'; drawPaged()")
    page.wait_for_timeout(500)
    assert columns(page) == 1
    assert order(page) == ['zeta', 'alpha', 'beta', 'gamma', 'delta', 'epsilon']
