"""The field preview stays above every editing tab and fits its panel."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'shared'))
from test_shared_ui_feedback import page, framework, ROOT


def test_field_preview_stays_above_editor(page):
    framework(page)
    source=(ROOT/'plugins/ff8/places.js').read_text(encoding='utf-8')
    detail=source[source.index('  function fieldDetail(row,prefs)'):source.index('  function buildFields()')]
    page.add_script_tag(content='''
      const state={fieldDetailTab:'background'}, row={_loaded:true,name:'Test field',key:'test',id:1};
      const fieldDetailTabs=[{id:'camera',label:'Camera'},{id:'walkmesh',label:'Walkmesh'}];
      const {el}=LexeditorUI;
      function sharedDetail(row,prefs,body){return LexeditorUI.detailPanel({title:row.name,body});}
      function fieldPreviewPanel(){
        const image=el('img',{src:'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="300" height="600"/>',class:'lex-overlay-base'});
        const overlay=el('canvas',{class:'lex-overlay-layer'});
        return {preview:LexeditorUI.imageMap({media:el('div',{class:'lex-overlay-stack'},image,overlay)}),
          editor:el('input',{'aria-label':'Tile',type:'number',value:0})};
      }
      function fieldDetailSubtab(row,active){return el('input',{'aria-label':active,type:'number',value:1});}
      function rerenderFields(){document.querySelector('main').replaceChildren(fieldDetail(row));}
    '''+detail+'rerenderFields();')
    page.add_style_tag(content='main {height:700px;width:950px;display:flex;}')
    for label in ['Camera','Walkmesh','Background']:
        page.locator('[role=tab]').filter(has_text=label).click()
        page.wait_for_function('document.querySelector(".lex-overlay-base").naturalHeight===600')
        image=page.locator('.lex-overlay-base').bounding_box()
        overlay=page.locator('.lex-overlay-layer').bounding_box()
        editor=page.locator('.lex-tabbed-panel').bounding_box()
        assert image['y']+image['height']<editor['y']
        assert abs(image['width']/image['height']-.5)<.01
        assert all(abs(image[key]-overlay[key])<1 for key in image)
        assert page.locator('.lex-tabbed-panel input').count()==1
        assert page.locator('.lex-panel-layout-vertical > .lex-detail-panel input').count()==0
