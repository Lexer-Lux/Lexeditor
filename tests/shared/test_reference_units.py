"""A reference beside a value with a unit shows the unit too.

Lexer: "your vanilla ref values are lacking the unit symbol after them. like
the armor percentages have no % after them." The unit lives on the unitField,
so every plugin that wraps a value in one gets it on its references.
"""
from test_shared_ui_feedback import page, framework


def reference_text(page, unit, position="suffix"):
    return page.evaluate('''([unit, position]) => {
      const U = LexeditorUI;
      const input = U.el('input', {type: 'number', value: 12, min: 0, max: 100});
      const control = U.provenanceControl({control: U.unitField(input, unit, {position}), vanilla: 7,
        internal: true, change: () => {}});
      const field = U.detailField({label: 'Absorption', control});
      document.querySelector('main').replaceChildren(U.el('div', {style: 'width:500px'}, field));
      U.refreshReferences(field);
      return field.querySelector('.lex-reference-value')?.textContent || '';
    }''', [unit, position])


def test_a_percentage_reference_reads_with_its_sign(page):
    framework(page)
    assert reference_text(page, '%') == 'V7%'


def test_a_word_unit_is_spaced_and_a_prefix_leads(page):
    framework(page)
    assert reference_text(page, 'G') == 'V7 G'
    assert reference_text(page, '$', 'prefix') == 'V$7'
