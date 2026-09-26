"""A NAME property that repeats the heading becomes the heading.

Lexer: "names should not be shown in the details panel as a property if the
header shows the name. instead, i should just be able to edit the name from
there."
"""
from test_shared_ui_feedback import page, framework


def test_name_property_moves_into_the_heading(page):
    framework(page)
    page.evaluate('''() => {
      const U = LexeditorUI, main = document.querySelector('main');
      window.renamed = [];
      const name = U.el('input', {type: 'text', value: 'Potion', oninput: e => window.renamed.push(e.target.value)});
      main.append(U.detailPanel({title: 'Potion', attrs: {id: 'moved'}, body: [
        U.detailSection({title: 'IDENTITY', body: [U.detailField({label: 'NAME', control: name})]}),
        U.detailSection({title: 'PRICES', body: [U.detailField({label: 'BUY', control: U.el('input', {type: 'number', value: 50})})]})]}));
      // A name that is not the heading's text is a different fact and stays.
      main.append(U.detailPanel({title: 'Potion', attrs: {id: 'kept'}, body: [
        U.detailSection({title: 'TEXT', body: [U.detailField({label: 'NAME', control: U.el('input', {type: 'text', value: 'Potion (Japanese)'})})]})]}));
    }''')
    page.wait_for_timeout(200)
    moved = page.locator('#moved')
    assert moved.locator('.lex-detail-panel-heading .lex-detail-panel-rename input').input_value() == 'Potion'
    assert moved.locator('.lex-detail-field-label-text', has_text='NAME').count() == 0
    assert moved.locator('.lex-detail-section-title', has_text='IDENTITY').count() == 0, 'an emptied section goes'
    assert moved.locator('.lex-detail-section-title', has_text='PRICES').count() == 1
    moved.locator('.lex-detail-panel-rename input').fill('Hi-Potion')
    assert page.evaluate('window.renamed.at(-1)') == 'Hi-Potion', 'the moved input still edits the record'
    kept = page.locator('#kept')
    assert kept.locator('.lex-detail-field-label-text', has_text='NAME').count() == 1
    assert kept.locator('.lex-detail-panel-rename').count() == 0
