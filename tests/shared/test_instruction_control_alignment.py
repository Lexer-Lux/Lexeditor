"""Opcode and operand controls share one baseline despite text fitting."""
from test_shared_ui_feedback import page, framework


def test_instruction_selects_keep_equal_height_with_reference_wrappers(page):
    framework(page)
    page.evaluate('''()=>{
      const U=LexeditorUI;
      const select=(label,size)=>U.el('select',{'aria-label':label,style:`font-size:${size}px`},U.el('option',{},label));
      document.querySelector('main').append(U.instructionList({rows:[{}],
        controls:()=>[
          select('Opcode',18),
          U.el('label',{class:'lex-instruction-operand'},'Target',select('Target',8)),
          U.el('label',{class:'lex-instruction-operand'},'Value',U.provenanceControl({
            control:select('Value',12),current:'Value',vanilla:'Other',apply(){}}))
        ],describe:()=> 'Instruction fixture'}));
    }''')
    boxes=page.locator('.lex-instruction-controls select').evaluate_all(
        'nodes=>nodes.map(n=>{const r=n.getBoundingClientRect();return {height:r.height,bottom:r.bottom}})')
    assert len(boxes)==3
    assert max(r['height'] for r in boxes)-min(r['height'] for r in boxes)<1, boxes
    assert max(r['bottom'] for r in boxes)-min(r['bottom'] for r in boxes)<1, boxes


def test_opcode_keeps_width_and_never_outgrows_operands(page):
    framework(page)
    page.evaluate('''()=>{
      const U=LexeditorUI,main=document.querySelector('main');main.style.width='720px';
      const fit=text=>U.autoFitControlText(U.el('select',{},U.el('option',{},text)));
      const operand=text=>U.el('label',{class:'lex-instruction-operand'},'Operand',fit(text));
      main.append(U.instructionList({rows:[1,4],
        controls:(count)=>[fit('If'),...Array.from({length:count},()=>operand('L0080'))],
        describe:()=>'A description long enough to want the whole row for itself'}));
    }''')
    page.wait_for_timeout(200)
    rows=page.locator('.lex-instruction-row').evaluate_all('''rows=>rows.map(row=>{
      const [opcode,...operands]=row.querySelectorAll('select');
      return {width:opcode.getBoundingClientRect().width,size:parseFloat(getComputedStyle(opcode).fontSize),
        operand:parseFloat(getComputedStyle(operands[0].closest('.lex-instruction-operand')).fontSize)}})''')
    assert rows[0]['width']==rows[1]['width'], rows
    assert all(row['size']<=row['operand']+.01 for row in rows), rows
