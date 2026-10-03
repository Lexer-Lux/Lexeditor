"""Editing one value must not refit untouched controls in a large panel."""
import pytest

from test_shared_ui_feedback import page, framework, ROOT


@pytest.mark.parametrize('count', [40, 400])
def test_numeric_edit_fitting_stays_with_edited_control(page, count):
    framework(page)
    page.evaluate('''count=>{
      const U=LexeditorUI,rows=[];
      for(let i=0;i<count;i++){
        const input=U.el('input',{type:'number',min:0,max:255,value:40+i%60});
        rows.push(U.detailField({label:`PROPERTY NUMBER ${i}`,dataType:'INT',min:0,max:255,
          control:U.provenanceControl({control:input,current:()=>Number(input.value),vanilla:25,
            references:[{name:'Reference Mod 1',shortName:'R1',value:30}],apply:v=>{input.value=v}})}));
      }
      document.querySelector('main').replaceChildren(U.detailSection({title:'Stress',body:rows}));
    }''', count)
    page.wait_for_timeout(600)
    result = page.evaluate('''async()=>{
      const inputs=[...document.querySelectorAll('input[type=number]')];
      const counts=inputs.map(()=>0);
      let layoutScans=0;
      for(const prototype of [Document.prototype,Element.prototype]){
        const original=prototype.querySelectorAll;
        prototype.querySelectorAll=function(selector){
          if(selector==='.lex-detail-field[data-lex-layout-field]')layoutScans++;
          return original.call(this,selector);
        };
      }
      inputs.forEach((input,i)=>{
        const measure=input.__lexAutoFitMeasure;
        input.__lexAutoFitMeasure=()=>{counts[i]++;return measure()};
      });
      for(let i=0;i<5;i++){
        inputs[0].value=String(30+i);
        inputs[0].dispatchEvent(new Event('input',{bubbles:true}));
        inputs[0].dispatchEvent(new Event('change',{bubbles:true}));
        await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
      }
      return {edited:counts[0],unrelated:counts.slice(1).reduce((a,b)=>a+b,0),layoutScans,
        values:inputs.slice(1).every((input,i)=>input.value===String(40+(i+1)%60))};
    }''')
    assert result['values']
    assert result['edited'] >= 5, result
    assert result['unrelated'] == 0, result
    assert result['layoutScans'] == 0, result


def test_loaded_font_refits_controls_and_mounted_reference_rails(page):
    pending=[]
    page.route('http://fixture/probe-font.ttf', lambda route: pending.append(route))
    framework(page)
    page.evaluate('''()=>{
      const U=LexeditorUI;
      window.probeFace=new FontFace('ProbeFont','url(http://fixture/probe-font.ttf)');
      document.fonts.add(probeFace);
      const input=U.el('input',{type:'number',min:0,max:255,value:88});
      const control=U.provenanceControl({control:input,current:()=>Number(input.value),
        vanilla:25,references:[{name:'Reference',shortName:'R1',value:30}],apply:value=>{input.value=value}});
      control.style.fontFamily='ProbeFont,monospace';input.style.fontFamily='ProbeFont,monospace';
      document.querySelector('main').replaceChildren(U.detailField({label:'Value',control}));
    }''')
    page.wait_for_function("document.querySelector('input').__lexAutoFitMeasure&&document.querySelector('.lex-source-control').style.getPropertyValue('--lex-internal-reference-requested-width')!==''")
    page.wait_for_timeout(100)
    assert pending
    page.evaluate('''()=>{
      const input=document.querySelector('input'),measure=input.__lexAutoFitMeasure;
      window.fontMeasurements=0;
      input.__lexAutoFitMeasure=()=>{fontMeasurements++;return measure()};
    }''')
    pending[0].fulfill(body=(ROOT/'ui/assets/fonts/Lexend-Variable.ttf').read_bytes(),content_type='font/ttf')
    page.wait_for_function("probeFace.status==='loaded'&&fontMeasurements>0")
    page.wait_for_timeout(100)
    assert page.evaluate('''()=>{
      const input=document.querySelector('input'),root=input.closest('.lex-source-control');
      const box=input.getBoundingClientRect(),text=root.querySelector('.lex-reference-text').getBoundingClientRect();
      return input.value==='88'&&text.left>=box.left&&text.right<=box.right;
    }''')
