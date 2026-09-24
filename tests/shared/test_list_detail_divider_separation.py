"""Resizable list/detail divider paints a visible separation line (F9)."""
from test_shared_ui_feedback import ROOT, framework, page  # noqa: F401  (pytest fixture)


def test_divider_gutter_carries_a_full_length_hairline(page):
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
    # The gutter is a transparent track over the body background; the hairline
    # is what reads as separation between the two panels at real settings.
    after = page.evaluate("""() => {
      const style = getComputedStyle(
        document.querySelector('.lex-panel-layout-divider'), '::after');
      return {content: style.content, width: style.width,
              background: style.backgroundColor};
    }""")
    assert after['content'] != 'none', after
    assert after['width'] == '1px', after
    swatch = page.evaluate("""() => {
      const probe = document.createElement('div');
      probe.style.background = 'var(--lex-border)';
      document.body.append(probe);
      return getComputedStyle(probe).backgroundColor;
    }""")
    assert after['background'] == swatch, (after, swatch)
    # The grip affordance stays on top of the gutter.
    before = page.evaluate("""() => getComputedStyle(
      document.querySelector('.lex-panel-layout-divider'), '::before').content""")
    assert before != 'none'
