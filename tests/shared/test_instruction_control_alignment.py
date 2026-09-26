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
