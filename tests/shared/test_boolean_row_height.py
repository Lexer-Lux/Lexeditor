"""Boolean rows stand as tall as number rows until references show.

Lexer's Navigation section (all booleans) ran visibly taller than its
number siblings: every boolean row reserved a 12px provenance gutter
whether or not it had references to show. The gutter now appears only
with actual reference values; the box itself matches input height.
"""
from test_shared_ui_feedback import ROOT, framework, page  # noqa: F401


def mount_rows(page, flag_vanilla):
    page.add_style_tag(path=str(ROOT / 'plugins/ds1/editor.css'))
    page.wait_for_timeout(300)
    page.evaluate('''flagVanilla => {
      document.documentElement.dataset.lexBooleanStyle = 'box';
      const U = LexeditorUI;
      const num = U.el('input', {type: 'number', value: 4});
      const flag = U.el('input', {type: 'checkbox', checked: true});
      const host = U.el('div', {style: 'width:600px'});
      host.append(
        U.detailField({label: 'Battle Distance: Short', property: 'short', control:
          U.provenanceControl({control: num, current: () => Number(num.value),
            vanilla: 4, internal: true, apply: () => {}})}),
        U.detailField({label: 'Can Navigate: Cliff', property: 'cliff', control:
          U.provenanceControl({control: flag, current: () => flag.checked ? 1 : 0,
            vanilla: flagVanilla, internal: true, apply: () => {}})}));
      document.querySelector('main').replaceChildren(host);
    }''', flag_vanilla)
    page.wait_for_timeout(250)


def heights(page):
    return page.locator('.lex-detail-field').evaluate_all(
        'ns=>ns.map(n=>Math.round(n.getBoundingClientRect().height))')


def test_boolean_row_matches_number_row_without_references(page):
    framework(page)
    mount_rows(page, 1)
    assert page.locator('.lex-boolean-field .lex-reference-values').count() == 0
    number, boolean = heights(page)
    assert abs(boolean - number) <= 1, (number, boolean)


def test_boolean_row_grows_when_references_show(page):
    framework(page)
    mount_rows(page, 1)
    short = heights(page)
    page.evaluate('''() => {
      const flag = document.querySelector('.lex-boolean-field input[type=checkbox]');
      flag.checked = false;
      flag.dispatchEvent(new Event('input', {bubbles: true}));
      LexeditorUI.refreshReferences();
    }''')
    page.wait_for_timeout(250)
    assert page.locator('.lex-boolean-field .lex-reference-values').is_visible()
    grown = heights(page)
    assert grown[1] - short[1] >= 10, (short, grown)
