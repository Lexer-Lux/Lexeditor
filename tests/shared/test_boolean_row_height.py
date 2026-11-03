"""Boolean provenance remains readable without moving neighboring rows.

Lexer's Navigation section (all booleans) ran visibly taller than its
number siblings: every boolean row reserved a 12px provenance gutter
whether or not it had references to show. References now share the value
box, and appearing or disappearing must not change the row height.
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


def test_boolean_row_stays_stable_when_references_show_and_hide(page, tmp_path):
    framework(page)
    mount_rows(page, 1)
    baseline = heights(page)
    flag = page.locator('.lex-boolean-field input[type=checkbox]')
    reference = page.locator('.lex-boolean-field .lex-reference-values')
    for checked in (False, True, False):
        flag.set_checked(checked)
        page.wait_for_timeout(100)
        assert reference.is_visible() is (not checked)
        current = heights(page)
        assert all(abs(left-right) <= 1 for left, right in zip(baseline, current)), (baseline, current)
        if not checked:
            assert reference.evaluate('''node=>{
              const row=node.closest('.lex-detail-field').getBoundingClientRect();
              const box=node.getBoundingClientRect();
              return box.width>0 && box.height>0 && box.left>=row.left && box.right<=row.right+1
                && box.top>=row.top && box.bottom<=row.bottom+1;
            }''')
    page.screenshot(path=str(tmp_path / 'stable-boolean-reference.png'))
