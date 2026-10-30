"""Pinning and reopening a many-column table must not freeze the UI.

The regression refitted all 213 rows for each cell ResizeObserver reported,
producing 13–15 second main-thread stalls without a plugin or server involved.
"""
import os
import pytest

from test_shared_ui_feedback import framework, page


@pytest.mark.parametrize('barrels',[5,6])
def test_pinned_numeric_column_and_repeated_navigation_stay_responsive(page,barrels):
    page.set_viewport_size({'width':2048,'height':1082})
    framework(page)
    page.evaluate('''barrels=>{
      const U=LexeditorUI;
      localStorage.clear();
      document.querySelector('main').style.height='100vh';
      window.frameGaps=[];
      let previous=performance.now();
      const tick=now=>{frameGaps.push(now-previous);previous=now;requestAnimationFrame(tick)};
      requestAnimationFrame(tick);
      window.records=Array.from({length:213},(_,index)=>({id:index,
        name:`Spell ${index}: Homing Crystal Soulmass`,values:{slots:index%20}}));
      window.paint=()=>document.querySelector('main').replaceChildren(U.pagedListDetail({
        rows:records,key:r=>r.id,selected:0,slots:false,noun:'spells',rowsKey:'spells',pageSize:40,
        defaultBarrels:barrels,minLeft:160,minRight:300,change:()=>paint(),
        master:({rows,selected,select})=>U.columnList({rows,key:r=>r.id,selected,select,
          columns:[{key:'name',label:'Name',grow:1}]}),
        describePinnedCell:()=>({editable:true,type:'number',numeric:true,minimum:0,maximum:255}),
        detail:r=>U.detailPanel({title:r.name,body:[U.detailField({label:'Slots Needed',property:'slots',
          control:U.el('input',{type:'number',min:0,max:255,value:r.values.slots})})]})}));
      paint();
    }''',barrels)
    page.locator('[data-lex-pin-column="slots"]').click(force=True)
    page.wait_for_timeout(100)
    assert page.locator('.lex-column-list-head-cell[data-column-key="pin:slots"]').count() == barrels
    for _ in range(3):
        page.evaluate('''async()=>{
          document.querySelector('main').replaceChildren(LexeditorUI.detailNote('Other tab'));
          await new Promise(requestAnimationFrame);
          paint();
          await new Promise(requestAnimationFrame);
          await new Promise(requestAnimationFrame);
        }''')
        page.wait_for_timeout(100)
    # A generous three-second ceiling tolerates slower CI machines while
    # detecting the observed multi-second frozen frames. Normal frames in
    # this fixture peak near 250 ms, including initial table construction.
    worst = page.evaluate('Math.max(...frameGaps)')
    assert worst < 3000, f'Table blocked the main thread for {worst:.0f} ms'
    assert page.locator('.lex-column-list-head-cell[data-column-key="pin:slots"]').count() == barrels
    cells = page.locator('.lex-column-list-row:not(.lex-filler-row) [data-column-key="pin:slots"]')
    assert cells.count() == min(213,barrels*40)
    assert cells.first.inner_text().strip() == '0'
    screenshot = os.environ.get('LEXEDITOR_PINNED_BARREL_SCREENSHOT')
    if screenshot and barrels == 5:
        page.screenshot(path=screenshot)
    page.locator('[data-lex-pin-column="slots"]').click(force=True)
    assert page.locator('.lex-column-list-head-cell[data-column-key="pin:slots"]').count() == 0
