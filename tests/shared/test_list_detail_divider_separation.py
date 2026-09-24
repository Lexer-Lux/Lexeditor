"""The resize grip remains available without a line through the panel gap."""
from test_shared_ui_feedback import ROOT, framework, page  # noqa: F401  (pytest fixture)


def test_divider_gutter_has_only_the_resize_grip(page):
    framework(page)
    page.evaluate("""() => {
      // Mirror framework.js settings application: panelGapPercent 0.5 -> 0.5vw.
      document.documentElement.style.setProperty('--lex-panel-gap', '0.5vw');
      const left = LexeditorUI.el('div', {class: 'lex-panel-layout-pane'});
      const right = LexeditorUI.el('div', {class: 'lex-panel-layout-pane'});
      document.querySelector('main').append(
        LexeditorUI.listDetail(left, right, 'f9-check'));
    }""")
    divider = page.locator('.lex-panel-layout-divider')
    assert divider.count() == 1
    box = divider.bounding_box()
    assert box['width'] > 0
    # Panel borders already separate the surfaces.
    after = page.evaluate("""() => {
      const style = getComputedStyle(
        document.querySelector('.lex-panel-layout-divider'), '::after');
      return {content: style.content, width: style.width,
              background: style.backgroundColor};
    }""")
    assert after['content'] == 'none', after
    # The grip affordance stays on top of the gutter.
    before = page.evaluate("""() => getComputedStyle(
      document.querySelector('.lex-panel-layout-divider'), '::before').content""")
    assert before != 'none'
