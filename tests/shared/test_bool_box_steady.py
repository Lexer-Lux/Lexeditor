"""Bool boxes hold still: the rail overlays the box and paints ticks."""
from test_shared_ui_feedback import page, framework

LIVE_MOUNT = '''([checked, vanilla]) => {
  const U = LexeditorUI;
  document.documentElement.dataset.lexBooleanStyle = 'box';
  const box = U.el('input', {type: 'checkbox'});
  box.checked = checked;
  document.querySelector('main').replaceChildren(U.detailField({label: 'Guard', dataType: 'BOOL',
    control: U.provenanceControl({control: box, current: () => box.checked,
      vanilla, references: [], apply: value => { box.checked = !!value; }})}));
}'''

STATIC_MOUNT = '''([current, vanilla]) => {
  const U = LexeditorUI;
  document.documentElement.dataset.lexBooleanStyle = 'box';
  document.querySelector('main').replaceChildren(U.detailField({label: 'Guard', dataType: 'BOOL',
    control: U.provenanceControl({control: U.el('input', {type: 'checkbox'}),
      current, vanilla, references: [], apply: () => {}})}));
}'''


def test_checkbox_vanilla_paints_ticks_not_digits(page):
    framework(page)
    page.evaluate(STATIC_MOUNT, [True, 0])
    rail = page.locator('.lex-reference-values')
    assert rail.count() == 1
    mark = rail.locator('.lex-boolean-mark.false')
    assert mark.count() == 1
    assert mark.inner_text() == '\u00d7'
    assert 'V 0' not in rail.inner_text()
    page.evaluate(STATIC_MOUNT, [False, 1])
    mark = page.locator('.lex-reference-values .lex-boolean-mark.true')
    assert mark.count() == 1
    assert mark.inner_text() == '\u2713'


def test_box_mode_keeps_field_padding_at_zero(page):
    framework(page)
    page.evaluate(LIVE_MOUNT, [True, False])
    field = page.locator('.lex-boolean-field')
    assert field.count() == 1
    assert page.locator('.lex-reference-values').count() == 1
    assert field.evaluate('n => getComputedStyle(n).paddingBottom') == '0px'
    page.evaluate("document.documentElement.dataset.lexBooleanStyle = 'arrow'")
    assert field.evaluate('n => getComputedStyle(n).paddingBottom') == '12px'


def test_checking_keeps_field_height(page):
    framework(page)
    page.evaluate(LIVE_MOUNT, [False, False])
    field = page.locator('.lex-boolean-field')
    before = field.evaluate('n => n.getBoundingClientRect().height')
    page.locator('input[type="checkbox"]').click()
    page.wait_for_selector('.lex-boolean-field .lex-reference-values')
    after = field.evaluate('n => n.getBoundingClientRect().height')
    assert after == before
