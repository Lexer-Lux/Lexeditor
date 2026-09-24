"""Resistance values stay readable when edited or switched to immunity."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'shared'))
from test_shared_ui_feedback import page,framework,ROOT


def test_defence_immunity_and_reference_layout(page):
    framework(page)
    page.add_style_tag(path=str(ROOT/'plugins/ff8/editor.css'))
    source=(ROOT/'plugins/ff8/party.js').read_text(encoding='utf-8')
    section=source[source.index('  const enemyDefencePrevious='):source.index('  const enemyScanElementNames=')]
    page.add_script_tag(content='''
      const {el,detailSection,infoHelp,unitField}=LexeditorUI;
      const state={activeSource:'mine',data:{enemyTables:{choices:{statuses:[{id:0,name:'Delayed petrify'},{id:1,name:'Float'}]}}}};
      const shell={refresh:()=>LexeditorUI.refreshReferences()};
      const conceptIcon=()=>el('img',{src:'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32" fill="purple"/></svg>'});
      const row={tables:{statusDefence:[{slot:0,percent:0,stored:100},{slot:1,percent:0,stored:100}]}};
      const vanilla=structuredClone(row);
      function enemyTableSource(control,row,read,apply,format){return LexeditorUI.provenanceControl({control,current:()=>read(row),vanilla:read(vanilla),apply,format});}
    '''+section+'''document.querySelector('main').append(enemyDefenceSection(row,'statusDefence','Status defence'));''')
    page.add_style_tag(content='main {width:480px;}')
    value=page.get_by_label('Delayed petrify defence percent',exact=True)
    page.wait_for_timeout(100)
    font=value.evaluate('e=>parseFloat(getComputedStyle(e).fontSize)')
    value.fill('90');value.blur()
    page.wait_for_timeout(100)
    assert value.evaluate('e=>parseFloat(getComputedStyle(e).fontSize)')>=font-1
    toggle=page.get_by_label('Delayed petrify immune',exact=True)
    toggle.check()
    assert value.is_disabled() and value.get_attribute('placeholder')=='Immune'
    assert value.input_value()==''
    assert page.evaluate('row.tables.statusDefence[0].stored')==255
    assert page.locator('.lex-icon-value-state').count()==0
    assert page.locator('.lex-icon-value-art').first.evaluate('e=>getComputedStyle(e).filter')=='grayscale(1)'
    boxes=page.locator('.lex-icon-value .lex-source-control').evaluate_all('es=>es.map(e=>e.getBoundingClientRect().top)')
    assert abs(boxes[0]-boxes[1])<1
    import tempfile
    page.locator('main').screenshot(path=str(Path(tempfile.gettempdir())/'lex-defence-immunity-review.png'))
    toggle.uncheck()
    assert value.input_value()=='90' and value.is_enabled()
    assert page.locator('.lex-source-control').evaluate_all('es=>es.every(e=>e.scrollWidth<=e.clientWidth+1)')
