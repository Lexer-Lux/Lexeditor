"""Filtering a shared list to zero rows preserves its detail pane geometry."""
from pathlib import Path
import tempfile

import pytest

from test_shared_ui_feedback import page, framework


@pytest.mark.parametrize('width', [900, 1600])
def test_empty_and_restored_details_fill_the_shared_pane(page, width):
    page.set_viewport_size({'width': width, 'height': 850})
    framework(page)
    page.evaluate('''() => {
      const U=LexeditorUI;
      window.authoredRows=Array.from({length:8},(_,id)=>({id,name:'Recipe '+id}));
      window.selectedRecord=null;
      const main=document.querySelector('main');main.style.height='700px';
      window.renderRecipeList=empty=>{window.emptyRecipeView=empty;main.replaceChildren(U.pagedListDetail({
        rows:empty?[]:authoredRows,key:row=>row.id,selected:3,noun:'recipes',
        splitKey:'empty-pane-check',slots:false,pageSize:8,
        master:v=>U.columnList({rows:v.rows,key:row=>row.id,selected:v.selected,
          columns:[{key:'name',label:'Recipe'}]}),
        detail:row=>U.detailPanel({title:row.name,body:U.detailSection({title:'OUTPUT',
          body:U.detailField({label:'AMOUNT',control:U.readonlyField('1')})})}),
        sync:v=>{selectedRecord=v.selected;},
        change:()=>requestAnimationFrame(()=>renderRecipeList(emptyRecipeView))
      }));};
      renderRecipeList(false);
    }''')
    for empty in [False, True, False]:
        page.evaluate('renderRecipeList', empty)
        page.wait_for_timeout(200)
        metrics=page.locator('.lex-paged-list-detail').evaluate('''root=>{
          const master=root.querySelector(':scope>.lex-barrelled-master'),
            detail=root.querySelector(':scope>.lex-detail'),
            m=master.getBoundingClientRect(),d=detail.getBoundingClientRect();
          return{masterHeight:m.height,detailHeight:d.height,topGap:d.top-m.top,
            bottomGap:d.bottom-m.bottom,selected:selectedRecord,
            title:detail.querySelector('.lex-detail-panel-title')?.textContent.trim(),
            rows:root.querySelectorAll('.lex-column-list-row:not(.lex-filler-row)').length,
            empty:!detail.childElementCount};
        }''')
        assert metrics['masterHeight'] > 400, metrics
        assert abs(metrics['topGap']) < 2 and abs(metrics['bottomGap']) < 2, metrics
        assert metrics['detailHeight'] > 400, metrics
        if empty:
            assert metrics['empty'] and metrics['selected'] is None and metrics['rows'] == 0, metrics
            output=Path(tempfile.gettempdir())/'lexeditor-dev'/'rendered'
            output.mkdir(parents=True,exist_ok=True)
            page.screenshot(path=str(output/f'empty-record-detail-{width}.png'))
        else:
            assert metrics['title']=='Recipe 3' and metrics['selected']==3 and metrics['rows']==8, metrics
    assert page.evaluate('authoredRows.map(row=>row.name)') == [f'Recipe {i}' for i in range(8)]
