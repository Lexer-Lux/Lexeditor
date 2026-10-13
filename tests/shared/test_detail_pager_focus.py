from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_shared_ui_feedback import page, framework


def test_detail_refit_keeps_the_focused_input_and_selection(page):
    framework(page)
    page.evaluate('''() => {
      const U=LexeditorUI;
      document.querySelector('main').style.cssText='width:600px;height:450px';
      document.querySelector('main').append(U.detailPanel({title:'Localization',body:[
        U.detailSection({title:'ADD KEY',body:[U.detailField({label:'KEY',
          control:U.el('input',{type:'text',value:'Greeting','aria-label':'New key'})})]})
      ]}));
    }''')
    field = page.get_by_label('New key', exact=True)
    field.focus()
    page.wait_for_timeout(100)
    field.evaluate('input=>input.setSelectionRange(1,4)')
    page.evaluate('''()=>{
      document.querySelector('.lex-tweaks-paged').lexFitPage();
      document.querySelector('main').style.width='550px';
    }''')
    page.wait_for_timeout(200)
    assert field.is_visible()
    assert field.evaluate('input=>input===document.activeElement')
    assert field.evaluate('input=>[input.selectionStart,input.selectionEnd]') == [1, 4]
    field.fill('Changed key')
    page.evaluate("document.querySelector('.lex-tweaks-paged').lexFitPage()")
    assert field.input_value() == 'Changed key'
    assert field.evaluate('input=>input===document.activeElement')
