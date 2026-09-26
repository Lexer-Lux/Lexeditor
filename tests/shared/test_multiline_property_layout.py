"""Multiline properties keep their label above the full-width editor."""
import os
from test_shared_ui_feedback import page, framework, ROOT


def test_multiline_labels_stack_with_provenance_and_pins(page):
    framework(page)
    page.add_style_tag(path=str(ROOT/'plugins/ff8/editor.css'))
    page.evaluate('''()=>{
      const U=LexeditorUI,main=document.querySelector('main');
      const prefs=U.columnPreferences('multiline',[{key:'description',label:'Description',pinned:false}]);
      main.append(U.detailPanel({title:'Enemy',body:[
        U.detailField({label:'Description',pin:prefs.pinButton('description'),
          control:U.provenanceControl({control:U.textArea({value:'A long description',rows:4,'aria-label':'Description'}),
            current:()=> 'A long description',vanilla:'Original description',apply(){}})}),
        U.detailField({label:'Battle text',control:U.textArea({value:'Battle dialogue',rows:3})})]}));
    }''')
    for width in [800,350]:
        page.evaluate('w=>document.querySelector("main").style.width=w+"px"',width)
        page.wait_for_timeout(100)
        for field in page.locator('.lex-detail-field').all():
            assert field.evaluate('''e=>{
              const label=e.querySelector('.lex-detail-field-label').getBoundingClientRect();
              const control=e.querySelector('.lex-detail-field-control').getBoundingClientRect();
              const text=e.querySelector('textarea').getBoundingClientRect();
              return label.bottom<=control.top+1 && text.width>=control.width-4;
            }''')
        assert page.locator('.lex-detail-field-label').first.evaluate('e=>parseFloat(getComputedStyle(e).fontSize)>=12')
    page.get_by_role('textbox',name='Description',exact=True).fill('Changed description')
    assert page.get_by_role('textbox',name='Description',exact=True).input_value()=='Changed description'
    page.locator('.lex-detail-field').first.hover()
    if os.environ.get('LEX_TEXT_SCREENSHOT'):
        page.screenshot(path=os.environ['LEX_TEXT_SCREENSHOT'])
