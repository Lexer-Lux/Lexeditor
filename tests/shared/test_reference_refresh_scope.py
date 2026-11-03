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
