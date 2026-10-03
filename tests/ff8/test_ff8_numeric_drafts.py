"""Rejected FF8 numeric drafts never reach record callbacks or Save jobs."""
from pathlib import Path
import sys
import tempfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests' / 'shared'))
from test_shared_ui_feedback import page, framework


def controls(page):
    framework(page)
    source = (ROOT / 'plugins' / 'ff8' / 'core.js').read_text(encoding='utf-8')
    start, end = '  function numberControl(', '  function selectControl('
    assert source.count(start) == source.count(end) == 1
    page.add_script_tag(content='''
      const el=LexeditorUI.el,formatNumber=LexeditorUI.formatNumber,unitField=LexeditorUI.unitField;
      window.refreshes=0; const shell={refresh:()=>refreshes++};
    ''' + source[source.index(start):source.index(end)])
    page.evaluate('''()=>{
      window.edits=[];window.record={byte:7,position:-30,identity:4000000000,price:50,percent:2.5};
      for(const [key,min,max,step] of [
        ['byte',0,255,1],['position',-2147483648,2147483647,1],
        ['identity',0,4294967295,1],['price',0,655350,10],['percent',0,100,.1]]){
        const control=numberControl(record[key],min,max,step,value=>{record[key]=value;edits.push([key,value])},
          {'aria-label':key});
        document.querySelector('main').append(LexeditorUI.detailField({label:key,control}));
      }
      document.querySelector('main').append(LexeditorUI.el('button',{},'Leave field'));
    }''')
    page.wait_for_function("[...document.querySelectorAll('input')].every(n=>n.type==='number')")


@pytest.mark.parametrize('key,draft', [
    ('byte','256'),('byte','-1'),('byte','2.5'),('byte',''),
    ('position','-2147483649'),('identity','4294967296'),
    ('price','51'),('percent','2.55')])
def test_rejected_drafts_survive_blur_without_mutating_records(page,key,draft):
    controls(page)
    before=page.evaluate('JSON.stringify(record)')
    input=page.get_by_role('spinbutton',name=key,exact=True)
    input.fill(draft)
    input.press('Tab')
    assert input.input_value()==draft
    assert not input.evaluate('(n)=>n.checkValidity()')
    assert page.evaluate('JSON.stringify(record)')==before
    assert page.evaluate('edits')==[]
    input.press('ArrowUp')
    assert input.input_value()==draft
    assert page.evaluate('edits')==[]


def test_valid_values_and_native_stepping_keep_declared_precision(page):
    controls(page)
    byte=page.get_by_role('spinbutton',name='byte',exact=True)
    byte.fill('255')
    byte.press('ArrowUp')
    assert byte.input_value()=='255'
    byte.press('ArrowDown')
    assert page.evaluate('record.byte')==254
    price=page.get_by_role('spinbutton',name='price',exact=True)
    price.press('ArrowUp')
    assert page.evaluate('record.price')==60
    percent=page.get_by_role('spinbutton',name='percent',exact=True)
    percent.press('ArrowDown')
    assert percent.input_value()=='2.4'
    assert page.evaluate('record.percent')==2.4
    identity=page.get_by_role('spinbutton',name='identity',exact=True)
    identity.fill('4294967295')
    assert page.evaluate('record.identity')==4294967295
    assert identity.get_attribute('type')=='number'
    page.get_by_role('spinbutton',name='position',exact=True).fill('-2147483648')
    assert page.evaluate('record.position')==-2147483648
    output=Path(tempfile.gettempdir())/'lexeditor-dev'/'rendered'/'ff8-validated-numeric-controls.png'
    output.parent.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(output))


def test_linked_hit_rate_rejects_drafts_and_converts_valid_percentages(page):
    controls(page)
    page.evaluate('''()=>{
      window.hitRate=17;window.hitEdits=[];
      window.numericEvents=[];
      for(const name of ['focus','blur','input','change'])document.addEventListener(name,event=>{
        if(event.target.matches('input'))numericEvents.push([name,event.target.getAttribute('aria-label'),event.target.value]);
      },true);
      document.querySelector('main').append(ratio255Control(hitRate,value=>{
        hitRate=value;hitEdits.push(value);
      }));
    }''')
    percent=page.get_by_role('spinbutton',name='Hit rate percentage',exact=True)
    exact=page.get_by_role('spinbutton',name='Hit rate out of 255',exact=True)
    for control,partner,draft in ((exact,percent,'17.5'),(exact,percent,'256'),
                                 (percent,exact,'101'),(percent,exact,'2.555')):
        partner_before=partner.input_value()
        control.fill(draft)
        assert control.input_value()==draft, page.evaluate('numericEvents')
        control.press('Tab')
        assert control.input_value()==draft
        assert partner.input_value()==partner_before
        assert page.evaluate('hitRate')==17
        assert page.evaluate('hitEdits')==[]
    exact.fill('64')
    assert percent.input_value()=='25.1'
    assert page.evaluate('hitRate')==64
    percent.fill('50')
    assert exact.input_value()=='128'
    assert percent.input_value()=='50.2'
    assert page.evaluate('hitRate')==128
    assert page.evaluate('hitEdits')==[64,128]


def test_save_rejects_invalid_draft_before_any_jobs_or_sync(page):
    controls(page)
    source=(ROOT/'plugins'/'ff8'/'boot.js').read_text(encoding='utf-8')
    start,end='  async function saveAll(){','  function post('
    assert source.count(start)==source.count(end)==1
    page.add_script_tag(content='''
      const state={tab:'items',data:{},selected:{}};
      window.syncCalls=0;window.alerts=[];window.jobs=[];
      function syncEnemyScanDetails(){syncCalls++;throw Error('Reached save processing')}
      function setStatus(value){window.saveStatus=value}
      function showAlert(value){alerts.push(value)}
      function api(...args){jobs.push(args)}
    '''+source[source.index(start):source.index(end)])
    page.get_by_role('spinbutton',name='byte',exact=True).fill('8')
    page.get_by_role('spinbutton',name='price',exact=True).fill('51')
    error=page.evaluate("saveAll().then(()=>null,error=>error.message)")
    assert error=='Correct price before saving.'
    assert page.evaluate('syncCalls')==0
    assert page.evaluate('jobs')==[]
    assert page.evaluate('record.byte')==8
    assert page.evaluate('record.price')==50
    assert page.evaluate('saveStatus')=='Save failed'
    assert page.evaluate('alerts[0].items[0].issue')==error
    page.get_by_role('spinbutton',name='price',exact=True).fill('60')
    assert page.evaluate("saveAll().then(()=>null,error=>error.message)")=='Reached save processing'
    assert page.evaluate('syncCalls')==1
    # Unavailable controls and detached/hidden panels must not block Save.
    price=page.get_by_role('spinbutton',name='price',exact=True)
    price.fill('51')
    for mode in ('readOnly','disabled','hidden'):
        price.evaluate('''(n,mode)=>{
          n.readOnly=false;n.disabled=false;n.closest('.lex-detail-field').hidden=false;
          if(mode==='hidden')n.closest('.lex-detail-field').hidden=true;
          else n[mode]=true;
        }''',mode)
        assert page.evaluate("saveAll().then(()=>null,error=>error.message)")=='Reached save processing'
    assert page.evaluate('record.price')==60
