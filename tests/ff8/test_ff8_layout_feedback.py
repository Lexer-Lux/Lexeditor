"""Shared layout acceptance cases raised by the FF8 screens."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from test_shared_ui_feedback import ROOT, page, framework


def test_tabs_and_help_keep_centering_and_contrast(page):
    framework(page)
    page.add_style_tag(path=str(ROOT/'plugins/ff8/editor.css'))
    page.evaluate('''() => {
      const U=LexeditorUI;
      document.querySelector('main').append(U.subtabBar({active:'a',
        tabs:[{id:'a',label:'Cards'},{id:'b',label:'Players'}]}),
        U.detailSection({title:'STAT GROWTH',help:U.infoHelp('How the stat grows.'),body:[]}));
    }''')
    for button in page.locator('.lex-subtab-button').all():
        button.hover()
        metrics=button.evaluate('''n=>{const s=getComputedStyle(n),a=n.getBoundingClientRect(),b=n.querySelector('.lex-tab-label').getBoundingClientRect();
          return {radius:s.borderTopLeftRadius,gap:Math.abs((a.top+a.bottom-b.top-b.bottom)/2)} }''')
        assert metrics['radius']=='0px',metrics
        assert metrics['gap']<2,metrics
    help=page.locator('.lex-info-help > span')
    assert help.evaluate('n=>getComputedStyle(n).webkitTextStrokeWidth')=='0px'
    assert help.evaluate('n=>getComputedStyle(n).color')=='rgb(17, 17, 17)'


def test_eight_curves_fill_two_rows_of_four(page):
    page.set_viewport_size({'width':1800,'height':900})
    framework(page)
    page.evaluate('''() => {
      const U=LexeditorUI;
      const grid=U.curveGrid(...Array.from({length:8},(_,i)=>U.curveEditor({
        title:'Stat '+i,domain:{min:1,max:100},range:{min:0,max:100},evaluate:x=>x})));
      const panel=U.detailPanel({heading:false,body:[U.detailSection({title:'Growth',body:grid})]});
      panel.style.height='680px';document.querySelector('main').append(panel);
    }''')
    page.wait_for_timeout(250)
    result=page.locator('.lex-curve-editor').evaluate_all('ns=>ns.map(n=>n.getBoundingClientRect().toJSON())')
    assert len({round(r['top']) for r in result})==2,result
    assert len({round(r['left']) for r in result})==4,result
    panel=page.locator('.lex-detail-panel').bounding_box()
    assert result[-1]['bottom']<=panel['y']+panel['height'],result


def test_filled_detail_table_uses_remaining_height(page):
    framework(page)
    page.evaluate('''() => {
      const U=LexeditorUI,rows=Array.from({length:8},(_,id)=>({id,name:'Enemy '+id}));
      const panel=U.detailPanel({heading:false,body:[U.controlGroup([
        {label:'Stage',control:U.el('input',{type:'number',value:1})}]),
        U.columnList({fill:true,rows,columns:[{key:'name',label:'Enemy'}]})]});
      panel.style.height='650px';document.querySelector('main').append(panel);
    }''')
    page.wait_for_timeout(150)
    table=page.locator('.lex-column-list').bounding_box()
    panel=page.locator('.lex-detail-panel').bounding_box()
    assert 0<=panel['y']+panel['height']-table['y']-table['height']<20


def test_player_index_upgrades_area_only_cache(tmp_path):
    import json
    from unittest.mock import patch
    from plugins.ff8 import field_data as field
    (tmp_path/'field').mkdir()
    cache=tmp_path/'field/card-players.json'
    cache.write_text(json.dumps({'source':'fixture','keys':['garden']}))
    script=tmp_path/'map.jsm';script.write_bytes(b'fixture')
    state={'thread':None,'keys':None,'players':[],'scanned':0,'total':0,'error':None}
    with patch.object(field.paths,'BASELINE_ROOT',tmp_path), patch.object(field,'_card_scan',state), \
         patch.object(field,'_fingerprint',return_value='fixture'), \
         patch.object(field,'ensure_index',return_value={'rows':[{'key':'garden'}]}), \
         patch.object(field,'ensure_map_baseline',return_value=(script,None,None)), \
         patch.object(field,'_parse_card_players',return_value=[{'id':0,'entity':'Student','script':'talk',
             'params':[{'id':0,'name':'Deck ID','mode':'literal','value':201,'editable':True}]}]):
        field._card_player_scan()
    assert state['error'] is None
    # The deck each call names travels with the scan, so a deck can be shown
    # and grouped without loading any area in the browser.
    assert state['players']==[{'map':'garden','id':0,'entity':'Student','script':'talk',
                               'deckId':201,'deckMode':'literal'}]
    assert json.loads(cache.read_text())['players']==state['players']
    assert json.loads(cache.read_text())['version']==field.CARD_SCAN_VERSION


def test_a_variable_deck_argument_has_no_deck_number(tmp_path):
    import json
    from unittest.mock import patch
    from plugins.ff8 import field_data as field
    (tmp_path/'field').mkdir()
    script=tmp_path/'map.jsm';script.write_bytes(b'fixture')
    state={'thread':None,'keys':None,'players':[],'scanned':0,'total':0,'error':None}
    with patch.object(field.paths,'BASELINE_ROOT',tmp_path), patch.object(field,'_card_scan',state), \
         patch.object(field,'_fingerprint',return_value='fixture'), \
         patch.object(field,'ensure_index',return_value={'rows':[{'key':'garden'}]}), \
         patch.object(field,'ensure_map_baseline',return_value=(script,None,None)), \
         patch.object(field,'_parse_card_players',return_value=[{'id':0,'entity':'Student','script':'talk',
             'params':[{'id':0,'name':'Deck ID','mode':'variable','value':292,'editable':True}]}]):
        field._card_player_scan()
    assert state['players'][0]['deckId'] is None
    assert state['players'][0]['deckMode']=='variable'
