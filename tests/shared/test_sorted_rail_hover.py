"""A property the list is sorted by shows its type when pointed at.

Lexer: "if i hover a property that's being sorted by instead of showing its
type rail instead of the triangle, the triangle just disappears. no type rail".
The sorted rule hid the type name and the hover rule hid the triangle, so the
rail went blank.
"""
from test_shared_ui_feedback import page, framework


def test_sorted_field_swaps_triangle_for_type_on_hover(page):
    framework(page)
    page.evaluate('''() => {
      const U = LexeditorUI, box = U.el('div', {style: 'width:600px'});
      document.querySelector('main').append(box);
      box.append(U.detailField({label: 'Value', showType: true,
        control: U.el('input', {type: 'number', value: 20, min: 0, max: 99})}));
      box.append(U.detailField({label: 'Other', showType: true,
        control: U.el('input', {type: 'number', value: 3})}));
      box.querySelector('.lex-detail-field').dataset.lexSort = 'asc';
    }''')
    field = page.locator('.lex-detail-field').first
    rail = field.locator(':scope > .lex-field-type-rail')
    name = rail.locator('.lex-field-type-name')
    triangle = lambda: rail.evaluate("r => getComputedStyle(r, '::after').content")
    shown = lambda node: node.evaluate(
        "n => getComputedStyle(n).display !== 'none' && getComputedStyle(n).opacity")

    page.mouse.move(700, 700)
    page.wait_for_timeout(250)
    assert triangle() == '"▲"'
    assert shown(name) in (False, '0')

    field.locator('.lex-detail-field-label').hover()
    page.wait_for_timeout(250)
    assert triangle() in ('none', 'normal')
    assert shown(name) == '1', 'the type name replaces the triangle on hover'

    field.locator('input').focus()
    page.mouse.move(700, 700)
    page.wait_for_timeout(250)
    assert shown(rail.locator('.lex-field-type-range')) == '1', 'focus shows the range'
