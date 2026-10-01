"""Wide boolean boxes use the same pin corner as other value boxes."""
import pytest
from test_shared_ui_feedback import framework, page


@pytest.mark.parametrize('provenance',[False,True])
@pytest.mark.parametrize('width',[350,700])
def test_boolean_pin_follows_box_style(page,tmp_path,provenance,width):
    framework(page)
    page.evaluate('''({provenance,width})=>{
      const U=LexeditorUI,prefs=U.columnPreferences('bool-pin',[{key:'enabled',label:'Enabled',pinned:true}],()=>{});
      const input=U.el('input',{type:'checkbox',checked:true});
      const control=provenance?U.provenanceControl({control:input,current:()=>true,vanilla:false,apply:()=>{}}):input;
      document.querySelector('main').style.width=width+'px';
      document.querySelector('main').append(U.detailPanel({title:'Properties',body:
        U.detailField({label:'Enabled',control,pin:prefs.pinButton('enabled','Enabled')})}));
    }''',{'provenance':provenance,'width':width})
    for style in ['box','arrow','box']:
        page.evaluate('(s)=>document.documentElement.dataset.lexBooleanStyle=s',style)
        page.wait_for_timeout(150)
        geometry=page.locator('.lex-boolean-field').evaluate('''n=>{
          const input=n.querySelector('input').getBoundingClientRect(),pin=n.querySelector('.lex-column-pin').getBoundingClientRect();
          return {input:input.toJSON(),pin:pin.toJSON(),tip:pin.left+pin.width*3.71/24};
        }''')
        if style=='box':
            assert 0<=geometry['input']['right']-geometry['tip']<=16,geometry
        else:
            assert geometry['pin']['right']<=geometry['input']['left'],geometry
    page.screenshot(path=str(tmp_path/'boolean-pin.png'))
