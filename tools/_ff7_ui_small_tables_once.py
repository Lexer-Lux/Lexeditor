"""One-shot FF7 polish for single/tiny fixed datasets."""
from pathlib import Path

root=Path(__file__).resolve().parents[1]
editor=root/'games/ff7/editor.html'
text=editor.read_text(encoding='utf-8')
old='''  function integratedView(){
    const group=state.tab,query=state.query[group]||"",sort=state.sort[group]||{key:"id",dir:1};
    if(!state.records[group]?.length)return unavailableView();
    const needle=query.trim().toLocaleLowerCase();
    const rows=[...state.records[group]].filter(row=>!needle||recordSearchText(row).includes(needle)).sort((a,b)=>compareListValues(listSortValue(a,sort.key),listSortValue(b,sort.key))*sort.dir);
    if(!rows.some(row=>row.id===state.selected[group]))state.selected[group]=rows[0]?.id??null;
    return pagedListDetail({rows,key:row=>row.id,slots:false,selected:state.selected[group],page:state.page[group]||0,pageSize:state.pageSize[group]||12,noun:labels[group],className:"ff7-layout",splitKey:`ff7-${group}`,rowsKey:`ff7-${group}`,defaultSplit:50,minLeft:320,minRight:360,search:{key:`ff7-${group}`,value:query,label:`Search ${labels[group]}`,change:value=>{state.query[group]=value;state.page[group]=0;render()}},sync:next=>{state.page[group]=next.page;state.pageSize[group]=next.pageSize;if(next.selected!==null)state.selected[group]=next.selected},change:next=>{state.page[group]=next.page;state.pageSize[group]=next.pageSize;if(next.selected!==null)state.selected[group]=next.selected;render()},master:view=>listTable(view.rows,view.selected,view.select),detail:row=>recordDetail(row)});
  }
'''
new='''  function integratedView(){
    const group=state.tab,sourceRows=state.records[group]||[],query=state.query[group]||"",sort=state.sort[group]||{key:"id",dir:1};
    if(!sourceRows.length)return unavailableView();
    const needle=query.trim().toLocaleLowerCase();
    const rows=[...sourceRows].filter(row=>!needle||recordSearchText(row).includes(needle)).sort((a,b)=>compareListValues(listSortValue(a,sort.key),listSortValue(b,sort.key))*sort.dir);
    if(!rows.some(row=>row.id===state.selected[group]))state.selected[group]=rows[0]?.id??null;
    // A one-record dataset has no selection problem to solve. Giving half the
    // workspace to a one-row master is pure chrome, so show its editor directly.
    if(sourceRows.length===1&&rows.length===1)return recordDetail(rows[0]);
    // The shared paged table is optimized for pages of records and deliberately
    // fills its master pane. For genuinely tiny fixed FF7 tables (recruits and
    // growth-bonus families), use an ordinary master/detail instead so 2–4 rows
    // retain normal row height rather than being expanded across a full page.
    if(sourceRows.length<=4){
      const selected=rows.find(row=>row.id===state.selected[group])||rows[0];
      if(!selected)return unavailableView();
      const master=listTable(rows,selected.id,row=>{state.selected[group]=typeof row==="object"?row.id:row;render()});
      master.classList.add("ff7-compact-master");
      return LexeditorUI.listDetail(master,recordDetail(selected),"ff7-layout ff7-compact-layout",{splitKey:`ff7-${group}`,defaultSplit:42,minLeft:260,minRight:360});
    }
    return pagedListDetail({rows,key:row=>row.id,slots:false,selected:state.selected[group],page:state.page[group]||0,pageSize:state.pageSize[group]||12,noun:labels[group],className:"ff7-layout",splitKey:`ff7-${group}`,rowsKey:`ff7-${group}`,defaultSplit:50,minLeft:320,minRight:360,search:{key:`ff7-${group}`,value:query,label:`Search ${labels[group]}`,change:value=>{state.query[group]=value;state.page[group]=0;render()}},sync:next=>{state.page[group]=next.page;state.pageSize[group]=next.pageSize;if(next.selected!==null)state.selected[group]=next.selected},change:next=>{state.page[group]=next.page;state.pageSize[group]=next.pageSize;if(next.selected!==null)state.selected[group]=next.selected;render()},master:view=>listTable(view.rows,view.selected,view.select),detail:row=>recordDetail(row)});
  }
'''
if text.count(old)!=1: raise SystemExit(f'integratedView marker count {text.count(old)}')
editor.write_text(text.replace(old,new),encoding='utf-8')

test=root/'tools/verify_ff7_rendered_neutral.py'
tests=test.read_text(encoding='utf-8')
marker='target.RenderedTests.open = open_with_neutral\n'
if tests.count(marker)!=1: raise SystemExit('rendered insertion marker missing')
addition='''def test_small_fixed_datasets_do_not_stretch_or_overlap(self):
    self.install(); self.open(); self.page.set_viewport_size({"width":900,"height":620})

    # Single-record datasets use the whole editing surface instead of wasting
    # half of it on a one-row master table.
    for group in ("initialState","apMultiplier"):
        with self.subTest(single=group):
            self.navigate(group)
            self.assertEqual(self.page.locator('.ff7-detail').count(),1)
            self.assertEqual(self.page.locator('.ff7-table').count(),0)

    # Tiny multi-record datasets keep ordinary list rows. This guards the old
    # Cait Sith/Vincent overlay where both names occupied the same giant row.
    for group,count in (("recruits",2),("growthBonuses",3)):
        with self.subTest(tiny=group):
            self.navigate(group); self.page.wait_for_timeout(50)
            rows=self.page.locator('.ff7-compact-master .lex-column-list-row')
            self.assertEqual(rows.count(),count)
            boxes=rows.evaluate_all('(rows)=>rows.map(row=>{const r=row.getBoundingClientRect();return{top:r.top,bottom:r.bottom,height:r.height}})')
            self.assertTrue(all(20<=box['height']<=60 for box in boxes),(group,boxes))
            self.assertTrue(all(left['bottom']<=right['top']+1 for left,right in zip(boxes,boxes[1:])),(group,boxes))
    self.originals_unchanged()


'''
tests=tests.replace(marker,addition+marker)
assign='target.RenderedTests.test_dense_custom_views_fit_narrow_detail_pane = test_dense_custom_views_fit_narrow_detail_pane\n'
if tests.count(assign)!=1: raise SystemExit('assignment marker missing')
tests=tests.replace(assign,assign+'target.RenderedTests.test_small_fixed_datasets_do_not_stretch_or_overlap = test_small_fixed_datasets_do_not_stretch_or_overlap\n')
test.write_text(tests,encoding='utf-8')
