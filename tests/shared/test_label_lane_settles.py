"""A detail panel's label lane settles: no floor flip-flop, no churn.

The lane floor was drawn from the failing labels alone, so it dropped out
from under the labels that fit: the DS1 animations character panel traded
its lane between 71px and 85px (and its labels between 13px and 14px) on
every frame, visibly flickering during playback. The floor now answers
from every label's two-line need, so it lands once and the panel sits
still: no style writes after the fit settles.
"""
from test_shared_ui_feedback import page, framework  # noqa: F401

BUILD = """() => {
  const U = LexeditorUI, main = document.querySelector('main');
  main.style.width = '360px';
  const field = (label, value) => U.detailField({label,
    control: U.readonlyField(value, {'aria-label': label})});
  main.append(U.detailPanel({title: 'c1200', body: [U.detailSection({title: 'Character',
    body: [field('Character ID', 'c1200'), field('Binder', 'c1200.anibnd.dcx'),
      field('Animations', '2')]})]}));
}"""

WATCH = """() => {
  window.__mut = 0;
  window.__floors = new Set();
  const pane = document.querySelector('.lex-detail-panel-body');
  window.__floors.add(pane.style.getPropertyValue('--lex-detail-label-floor'));
  new MutationObserver(records => {
    window.__mut += records.length;
    window.__floors.add(pane.style.getPropertyValue('--lex-detail-label-floor'));
  }).observe(document.querySelector('main'),
    {childList: true, subtree: true, attributes: true, characterData: true});
}"""


def test_label_lane_settles_without_churn(page):
    framework(page)
    page.evaluate(BUILD)
    page.wait_for_timeout(1500)
    page.evaluate(WATCH)
    page.wait_for_timeout(1500)
    settled = page.evaluate("({mut: window.__mut, floors: [...window.__floors]})")
    assert settled["mut"] == 0, settled
    assert len(settled["floors"]) == 1, settled
