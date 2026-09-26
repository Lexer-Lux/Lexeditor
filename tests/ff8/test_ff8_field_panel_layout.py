"""The field preview sits beside the editing tabs, or above them in the Deling-style
layout, and fits its panel either way."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'shared'))
from test_shared_ui_feedback import page, framework, ROOT


def mount_field_detail(page, deling):
    framework(page)
    source=(ROOT/'plugins/ff8/places.js').read_text(encoding='utf-8')
    detail=source[source.index('  function fieldDetail(row,prefs)'):source.index('  function buildFields()')]
    page.add_script_tag(content='''
      const state={fieldDetailTab:'background',editorSettings:{delingFieldLayout:%s}}, row={_loaded:true,name:'Test field',key:'test',id:1};
      const fieldDetailTabs=[{id:'background',label:'Background'},{id:'camera',label:'Camera'},{id:'walkmesh',label:'Walkmesh'}];
      const {el,infoHelp}=LexeditorUI;
      function sharedDetail(row,prefs,body){return LexeditorUI.detailPanel({title:row.name,body});}
      function fieldPreviewView(){
        const image=el('img',{src:'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="300" height="600"/>',class:'lex-overlay-base'});
        const overlay=el('canvas',{class:'lex-overlay-layer'});
        return LexeditorUI.imageMap({media:el('div',{class:'lex-overlay-stack'},image,overlay)});
      }
      function fieldDetailSubtab(row,active){return el('input',{'aria-label':active,type:'number',value:1});}
      function rerenderFields(){document.querySelector('main').replaceChildren(fieldDetail(row));}
    ''' % ('true' if deling else 'false')+detail+'rerenderFields();')
    # The plugin's own sheet places the picture's help pip in its corner.
    sheet=(ROOT/'plugins/ff8/editor.css').read_text(encoding='utf-8')
    page.add_style_tag(content=next(line for line in sheet.splitlines() if '.field-preview-help' in line))
    page.add_style_tag(content='main {height:700px;width:950px;display:flex;}')


def check_every_tab(page, placed):
    for label in ['Camera','Walkmesh','Background']:
        page.locator('[role=tab]').filter(has_text=label).click()
        page.wait_for_function('document.querySelector(".lex-overlay-base").naturalHeight===600')
        image=page.locator('.lex-overlay-base').bounding_box()
        overlay=page.locator('.lex-overlay-layer').bounding_box()
        editor=page.locator('.lex-tabbed-panel').bounding_box()
        assert placed(image,editor), (label,image,editor)
        assert abs(image['width']/image['height']-.5)<.01
        assert all(abs(image[key]-overlay[key])<1 for key in image)
        assert page.locator('.lex-detail-panel-media .lex-detail-panel-meta').count()==0
        assert page.locator('.lex-detail-panel-media > .field-preview-help').count()==1
        assert page.locator('.lex-tabbed-panel input').count()==1
        assert page.locator('.lex-panel-layout > .lex-detail-panel input').count()==0


def test_field_preview_is_a_column_beside_the_editor(page):
    mount_field_detail(page, deling=False)
    check_every_tab(page, lambda image, editor: image['x']+image['width']<=editor['x'])


def test_deling_style_layout_stacks_the_preview_above_the_editor(page):
    mount_field_detail(page, deling=True)
    check_every_tab(page, lambda image, editor: image['y']+image['height']<editor['y'])
    image=page.locator('.lex-overlay-base').bounding_box()
    pane=page.locator('.lex-detail-panel-media').bounding_box()
    assert abs(image['height']-pane['height'])<3


def test_field_camera_projection_uses_view_translation_and_uniform_axes(page):
    source=(ROOT/'plugins/ff8/places.js').read_text(encoding='utf-8')
    project=source[source.index('  function fieldProject('):source.index('  function fieldOverlayCameraId(')]
    page.add_script_tag(content=project)
    result=page.evaluate('''()=>{const camera={axis:[{x:4096,y:0,z:0},{x:0,y:4096,z:0},{x:0,y:0,z:4096}],position:{x:0,y:0,z:100},zoom:200};
      return [fieldProject(camera,{x:10,y:20,z:0}),fieldProject(camera,{x:0,y:0,z:-200}),
        fieldProject({...camera,position:{x:10,y:20,z:100}},{x:-10,y:-20,z:0})];}''')
    assert result[0]=={'x':20,'y':40}
    assert result[1] is None
    assert result[2]=={'x':0,'y':0}
