"""Changed property labels follow the value's provenance and reset on revert."""
from test_shared_ui_feedback import framework, page


def test_modified_property_label_reverts_with_value(page, tmp_path):
    framework(page)
    page.evaluate('''() => {
      document.documentElement.style.setProperty('--lex-accent-ink','#ee2277');
      const U=LexeditorUI;
      window.value=12;
      window.control=U.provenanceControl({control:U.el('input',{value:12}),
        current:()=>value,vanilla:10,apply:v=>value=v});
      document.querySelector('main').append(U.detailField({label:'Price',control}),
        U.detailField({label:'Unchanged',control:U.el('input',{value:10})}));
    }''')
    labels = page.locator('.lex-detail-field-label-text')
    assert labels.nth(0).evaluate('n=>getComputedStyle(n).color') == 'rgb(238, 34, 119)'
    assert labels.nth(1).evaluate('n=>getComputedStyle(n).color') != 'rgb(238, 34, 119)'
    page.screenshot(path=str(tmp_path / 'changed-label.png'))
    page.evaluate('value=10;control.refreshReference()')
    assert labels.nth(0).evaluate('n=>getComputedStyle(n).color') != 'rgb(238, 34, 119)'
