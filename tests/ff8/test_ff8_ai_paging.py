"""AI paging and reordering preserve full-script positions and a fixed footer."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from test_shared_ui_feedback import ROOT, page, framework


def test_later_page_actions_use_full_script_indices(page):
    framework(page)
    source=(ROOT/'plugins/ff8/party.js').read_text(encoding='utf-8')
    renderer=source[source.index('  function enemyAiScript('):source.index('  function enemyAiSourceReference(')]
    page.add_script_tag(content='''
      const state={activeSource:'mine'},el=LexeditorUI.element;
      const enemyAiNormalizeScript=()=>{},enemyAiCatalog=()=>[];
      const enemyAiOpcodeControl=()=>el('select');
      const enemyAiOperand=()=>el('input');
      const enemyAiDescription=(r,i)=>'Instruction '+i.offset;
      const enemyAiMove=(s,index,direction)=>window.moved=[index,direction];
      const enemyAiInsert=(s,index)=>window.inserted=index;
      const enemyAiDelete=(s,index)=>{s.instructions.splice(index,1);renderEnemies()};
      const row={id:7},script={id:2,name:'Turn',instructions:Array.from({length:1000},(_,i)=>
        ({offset:i,label:'Instruction '+i,raw:'00',editable:true,operands:[]}))};
      function renderEnemies(){const view=enemyAiScript(row,script);view.style.height='600px';document.querySelector('main').replaceChildren(view)}
    '''+renderer)
    page.evaluate('renderEnemies()')
    page.wait_for_timeout(150)
    count=page.locator('[data-offset]').count()
    assert 1<count<12
    footer=page.locator('.lex-instruction-footer').bounding_box()
    page.get_by_role('button',name='Next page',exact=True).click()
    assert page.locator('[data-offset]').first.get_attribute('data-offset')==str(count)
    assert page.locator('.lex-instruction-footer').bounding_box()==footer
    assert page.locator('.lex-instruction-handle').count()==0
    page.locator('.lex-instruction-row').first.focus()
    page.keyboard.press('Alt+ArrowUp')
    assert page.evaluate('window.moved')==[count,-1]
    page.locator('.lex-instruction-actions button').first.click()
    assert page.evaluate('window.inserted')==count
    page.locator('.lex-instruction-description').first.drag_to(page.locator('.lex-instruction-row').nth(2))
    assert page.evaluate('window.moved')==[count,2]
    # Editing an operand must not start a row drag or reorder from Alt+arrows.
    page.evaluate('''()=>{
      const row=document.querySelector('.lex-instruction-row'),control=row.querySelector('select');
      control.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));
      window.inputDragAllowed=row.dispatchEvent(new DragEvent('dragstart',{bubbles:true,cancelable:true,dataTransfer:new DataTransfer()}));
    }''')
    assert page.evaluate('window.inputDragAllowed') is False
    page.locator('.lex-instruction-controls select').first.press('Alt+ArrowUp')
    assert page.evaluate('window.moved')==[count,2]
    page.get_by_role('button',name='Last page',exact=True).click()
    page.locator('.lex-instruction-actions button').nth(1).click()
    assert page.evaluate('script.instructions.length')==999
    page.get_by_role('button',name='First page',exact=True).click()
    assert page.locator('[data-offset]').first.get_attribute('data-offset')=='0'
    page.set_viewport_size({'width':700,'height':500})
    page.evaluate("document.querySelector('.lex-instruction-pane').style.height='320px'")
    page.wait_for_timeout(200)
    rows=page.locator('.lex-instruction-row')
    assert rows.count()<count
    last=rows.last.bounding_box();footer=page.locator('.lex-instruction-footer').bounding_box()
    assert last['y']+last['height']<=footer['y']+1


def test_curve_drawer_is_one_row_at_bottom(page):
    framework(page)
    page.evaluate('''() => {
      const U=LexeditorUI,graph=U.curveEditor({title:'HP',domain:{min:1,max:100},range:{min:0,max:100},evaluate:x=>x,
        variables:['A','B','C','D'].map(label=>({label,control:U.el('input',{type:'number',value:2})}))});
      graph.style.width='380px';graph.style.height='240px';document.querySelector('main').append(graph);
    }''')
    drawer=page.locator('.lex-curve-variables')
    assert drawer.evaluate('n=>Number(getComputedStyle(n).opacity)')==0
    page.locator('.lex-curve-editor').hover()
    page.wait_for_timeout(200)
    boxes=page.locator('.lex-curve-variable').evaluate_all('ns=>ns.map(n=>n.getBoundingClientRect().toJSON())')
    assert len({round(box['top']) for box in boxes})==1
    graph=page.locator('.lex-curve-editor').bounding_box();box=drawer.bounding_box()
    assert abs(box['y']+box['height']-graph['y']-graph['height'])<2
    page.locator('.lex-curve-variable input').first.focus()
    page.mouse.move(1000,700)
    assert drawer.evaluate('n=>Number(getComputedStyle(n).opacity)')==1
