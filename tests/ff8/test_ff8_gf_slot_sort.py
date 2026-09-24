import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from test_shared_ui_feedback import ROOT, page, framework


def test_slot_header_sorts_numerically_both_directions(page):
    framework(page)
    source=(ROOT/'plugins/ff8/party.js').read_text(encoding='utf-8')
    abilities=source[source.index('  function gfAbilities('):source.index('  function renderGFs(')]
    sort=source[source.index('  function sortGfTable('):source.index('  // GF compatibility')]
    page.add_script_tag(content='''
      const {columnList,detailSection}=LexeditorUI;
      const state={gfSorts:{abilities:['ability',1]}};
      const fields=[10,2,1].map((slot,i)=>({field:'ability'+slot,row:'ability'+slot,value:i}));
      const displayFieldValue=field=>field?.value??'';
      const fieldSourceControl=field=>LexeditorUI.readonlyField(field.value);
      function renderGFs(){document.querySelector('main').replaceChildren(gfAbilities(fields,{id:0}));}
    '''+sort+abilities+'renderGFs();')
    slots=lambda:page.locator('.lex-column-list-row').evaluate_all("rows=>rows.map(r=>Number(r.dataset.key.replace('ability','')))")
    assert slots()==[10,2,1]
    header=page.locator('.lex-column-list-head-cell').first
    header.locator('.lex-column-sort').click()
    assert slots()==[1,2,10]
    header.locator('.lex-column-sort').click()
    assert slots()==[10,2,1]
    assert page.evaluate('fields.map(f=>f.value)')==[0,1,2]
