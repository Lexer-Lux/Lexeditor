"""Shared text areas grow to show their content without a manual resize."""
from test_shared_ui_feedback import page,framework


def test_text_area_grows_with_content_and_width(page):
    framework(page)
    page.evaluate('''()=>{document.querySelector('main').style.width='480px';
      document.querySelector('main').append(LexeditorUI.el('div',{},LexeditorUI.textArea({'aria-label':'Description',value:'A short description.'})));}''')
    box=page.get_by_label('Description')
    initial=box.bounding_box()['height']
    box.fill(('This is a long description which must remain readable. '*12).strip())
    assert box.bounding_box()['height']>initial
    assert box.evaluate('e=>e.scrollHeight<=e.clientHeight+1')
    page.evaluate('document.querySelector("main").style.width="240px"')
    assert box.evaluate('e=>e.scrollHeight<=e.clientHeight+1')


def test_text_reference_stays_below_editor(page):
    framework(page)
    page.evaluate('''()=>{document.querySelector('main').append(LexeditorUI.provenanceControl({
      control:LexeditorUI.textArea({value:'Changed description'}),current:()=> 'Changed description',
      vanilla:'Original description',apply:()=>{}}));}''')
    text=page.locator('textarea').bounding_box()
    reference=page.locator('.lex-reference-values').bounding_box()
    assert reference['y']>=text['y']+text['height']-1
    assert page.locator('textarea').evaluate('e=>e.clientWidth>=e.parentElement.clientWidth-4')
