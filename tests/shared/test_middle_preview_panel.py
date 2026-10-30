"""Record selection and pinning keep the shared middle preview alive."""
import os
from test_shared_ui_feedback import framework,page


def test_middle_preview_survives_selection_and_pin_changes(page):
    framework(page)
    page.evaluate('''() => {
      const U=LexeditorUI;
      const preview=U.el('div',{'data-preview':'',style:'min-height:300px'},'Map preview');
      preview.token={stable:true};window.preview=preview;
      const rows=[{id:0,name:'Vertex 0',values:{x:0}},{id:1,name:'Vertex 1',values:{x:2}}];
      let view;
      // names: vertices use array indices and have no stored names.
      view=U.pagedListDetail({rows,key:row=>row.id,selected:0,slots:false,noun:'vertices',
        rowsKey:'middle-preview',splitKey:'middle-preview',pageSize:10,
        masterHeader:U.el('div',{'data-master-header':''},'Vertices'),middlePanel:()=>preview,
        change:next=>{if(next.reason==='pins')view.refreshMaster();},
        master:({rows,selected,select})=>U.columnList({rows,key:row=>row.id,selected,select,
          columns:[{key:'name',label:'Name',grow:1}]}),
        detail:row=>U.detailPanel({title:row.name,body:[U.detailField({label:'X',property:'x',
          control:U.el('input',{'aria-label':'X',type:'number',min:-100,max:100,value:row.values.x})})]})});
      document.querySelector('main').append(view);window.view=view;
    }''')
    page.get_by_text('Vertex 1',exact=True).first.click()
    assert page.get_by_role('spinbutton',name='X',exact=True).input_value() == '2'
    assert page.evaluate('document.querySelector("[data-preview]")===preview&&preview.token.stable')
    assert page.locator('[data-master-header]').count() == 1
    page.locator('[data-lex-auto-pin]').first.click()
    page.wait_for_function('document.querySelector(".lex-barrel-grid").innerText.includes("X")')
    assert page.evaluate('document.querySelector("[data-preview]")===preview&&preview.token.stable')
    assert page.locator('[data-master-header]').count() == 1
    boxes = page.evaluate('''() => ['.lex-barrelled-master','[data-preview]','.lex-detail-panel']
      .map(selector=>{const r=document.querySelector(selector).getBoundingClientRect();return {x:r.x,width:r.width};})''')
    assert boxes[0]['x'] < boxes[1]['x'] < boxes[2]['x']
    if os.environ.get('LEX_MIDDLE_PREVIEW_CAPTURE'):
        page.screenshot(path=os.environ['LEX_MIDDLE_PREVIEW_CAPTURE'])
