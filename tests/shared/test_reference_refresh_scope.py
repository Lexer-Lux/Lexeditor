"""A shell reference refresh must not rebuild strips on untouched controls."""
import pytest

from test_shared_ui_feedback import framework, page


@pytest.mark.parametrize('count', [40, 400])
def test_value_edits_preserve_untouched_reference_nodes(page, count):
    framework(page)
    page.evaluate('''count => {
      const U=LexeditorUI;
      window.referenceInputs=[];window.referenceRoots=[];
      const rows=[];
      for(let index=0;index<count;index++){
        const input=U.el('input',{type:'number',value:40+(index%60)});
        const root=U.provenanceControl({control:input,current:()=>Number(input.value),
          vanilla:25,references:[{name:'Reference',shortName:'R1',value:30}],apply:value=>{input.value=value}});
        referenceInputs.push(input);referenceRoots.push(root);
        rows.push(U.detailField({label:`Property ${index}`,control:root}));
      }
      document.querySelector('main').replaceChildren(U.detailSection({body:rows}));
    }''', count)
    result=page.evaluate('''async () => {
      const untouched=referenceRoots.slice(1).map(root=>root.querySelector(':scope > .lex-reference-values'));
      const replaced=new Set();
      const observer=new MutationObserver(records=>{
        for(const record of records){
          const index=referenceRoots.indexOf(record.target);
          if(index>=0&&[...record.removedNodes].some(node=>node.classList?.contains('lex-reference-values')))
            replaced.add(index);
        }
      });
      observer.observe(document.querySelector('main'),{childList:true,subtree:true});
      for(let value=30;value<35;value++){
        referenceInputs[0].value=String(value);
        referenceInputs[0].dispatchEvent(new Event('input',{bubbles:true}));
        referenceInputs[0].dispatchEvent(new Event('change',{bubbles:true}));
        LexeditorUI.refreshReferences();
        await new Promise(resolve=>requestAnimationFrame(resolve));
      }
      observer.disconnect();
      return {replaced:[...replaced],preserved:untouched.every((node,index)=>
        node===referenceRoots[index+1].querySelector(':scope > .lex-reference-values')),
        displayed:referenceRoots[0].querySelector('.lex-reference-values').textContent};
    }''')
    assert result['preserved'] and result['replaced']==[0], result
    assert '25' in result['displayed'] and '30' in result['displayed'], result


def test_edit_keeps_its_reference_rail_when_the_comparisons_do_not_change(page, tmp_path):
    framework(page)
    page.evaluate('''()=>{
      const U=LexeditorUI;
      window.input=U.el('input',{type:'number',min:0,max:255,value:40});
      window.root=U.provenanceControl({control:input,current:()=>Number(input.value),
        vanilla:25,references:[{name:'Reference',shortName:'R1',value:30}],apply:value=>{input.value=value}});
      document.querySelector('main').append(U.detailField({label:'Value',control:root}));
      window.rail=root.querySelector('.lex-reference-values');
    }''')
    result=page.evaluate('''()=>{
      const edit=value=>{input.value=String(value);input.dispatchEvent(new Event('input',{bubbles:true}));
        input.dispatchEvent(new Event('change',{bubbles:true}));LexeditorUI.refreshReferences();};
      for(const value of [41,42,43])edit(value);
      const reused=rail===root.querySelector('.lex-reference-values');
      edit(25);
      const vanilla={modified:root.classList.contains('lex-value-modified'),
        slots:[...root.querySelectorAll('.lex-reference-value')].map(node=>node.dataset.referenceIndex)};
      edit(30);
      const reference={modified:root.classList.contains('lex-value-modified'),
        slots:[...root.querySelectorAll('.lex-reference-value')].map(node=>node.dataset.referenceIndex)};
      return {reused,vanilla,reference};
    }''')
    assert result['reused'], result
    assert result['vanilla']=={'modified':False,'slots':['1']}, result
    assert result['reference']=={'modified':True,'slots':['0']}, result
    page.screenshot(path=str(tmp_path/'reference-rail-stable.png'))
