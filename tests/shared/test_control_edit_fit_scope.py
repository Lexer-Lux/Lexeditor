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
      let layoutScans=0,markerScans=0;
      for(const prototype of [Document.prototype,Element.prototype]){
        const original=prototype.querySelectorAll;
        prototype.querySelectorAll=function(selector){
          if(selector==='.lex-detail-field[data-lex-layout-field]')layoutScans++;
          if(this instanceof Document&&selector.startsWith('.lex-shell-header nav button.active,'))markerScans++;
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
      return {edited:counts[0],unrelated:counts.slice(1).reduce((a,b)=>a+b,0),layoutScans,markerScans,
        values:inputs.slice(1).every((input,i)=>input.value===String(40+(i+1)%60))};
    }''')
    assert result['values']
    assert result['edited'] >= 5, result
    assert result['unrelated'] == 0, result
    assert result['layoutScans'] == 0, result
    assert result['markerScans'] == 0, result


def test_reference_follows_its_value_size(page):
    framework(page)
    page.evaluate("""() => {
      const U = LexeditorUI;
      const input = U.el('input', {type: 'number', min: 0, max: 999999999, value: 123456789});
      const field = U.detailField({label: 'Value', control: U.provenanceControl({control: input,
        internal: true, current: () => Number(input.value), vanilla: 25,
        apply: v => { input.value = v; }})});
      const main = document.querySelector('main');
      main.replaceChildren(U.detailSection({title: 'Narrow', body: [field]}));
      main.style.width = '120px';
    }""")
    page.wait_for_function("document.querySelector('input').style.fontSize !== ''")
    page.wait_for_timeout(300)
    sizes = page.evaluate("""() => {
      const input = document.querySelector('input');
      const overlay = document.querySelector('.lex-source-control-internal > .lex-reference-values');
      const text = overlay.querySelector('.lex-reference-text');
      return {input: input.style.fontSize, overlay: overlay.style.fontSize,
        text: getComputedStyle(text).fontSize, natural: getComputedStyle(document.body).fontSize};
    }""")
    assert sizes['input'] and sizes['input'] == sizes['overlay'], sizes
    assert float(sizes['input'].replace('px', '')) < float(sizes['natural'].replace('px', '')), sizes
    assert float(sizes['text'].replace('px', '')) <= float(sizes['input'].replace('px', '')), sizes


def test_removed_dragger_releases_scope_survivors(page):
    framework(page)
    page.evaluate("""() => {
      const U = LexeditorUI;
      const make = value => U.detailField({label: 'Value', dataType: 'INT', min: 0, max: 255,
        control: U.el('input', {type: 'number', min: 0, max: 255, value})});
      const main = document.querySelector('main');
      main.replaceChildren(U.detailSection({title: 'Scope', body: [make('7'), make('12')]}));
      main.style.width = '300px';
    }""")
    page.wait_for_function(
        "document.querySelectorAll('input').length === 2 && "
        "[...document.querySelectorAll('input')].every(i => i.style.fontSize !== '')")
    page.wait_for_timeout(300)
    natural = page.evaluate(
        "[...document.querySelectorAll('input')].map(i => getComputedStyle(i).fontSize)")
    page.evaluate("""() => {
      const U = LexeditorUI;
      const section = document.querySelector('.lex-detail-section');
      const field = U.detailField({label: 'Dragger',
        control: U.el('input', {type: 'text', value: '9'.repeat(60)})});
      section.append(field);
      // Text boxes do not self-register; the suite registers this one.
      U.autoFitControlText(field.querySelector('input'), {minimum: 8});
    }""")
    page.wait_for_function(
        "[...document.querySelectorAll('input')].every(i => parseFloat(getComputedStyle(i).fontSize) < 10)")
    dragged = page.evaluate(
        "[...document.querySelectorAll('input')].map(i => getComputedStyle(i).fontSize)")
    assert all(size != natural[0] for size in dragged), (natural, dragged)
    page.evaluate("""() => {
      const inputs = [...document.querySelectorAll('input')];
      inputs[inputs.length - 1].closest('.lex-detail-field').remove();
    }""")
    page.wait_for_function(
        f"[...document.querySelectorAll('input')].every(i => getComputedStyle(i).fontSize === '{natural[0]}')",
        timeout=10000)
    assert page.evaluate(
        "[...document.querySelectorAll('input')].map(i => getComputedStyle(i).fontSize)") == natural


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
