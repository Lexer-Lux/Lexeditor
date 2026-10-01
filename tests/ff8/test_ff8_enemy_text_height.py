"""Enemy text fits its content rather than reserving empty lines."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'shared'))
from test_shared_ui_feedback import ROOT, framework, page


def test_short_enemy_text_fits_and_long_text_grows(page, tmp_path):
    framework(page)
    page.add_style_tag(path=str(ROOT / 'plugins/ff8/editor.css'))
    source = (ROOT / 'plugins/ff8/party.js').read_text(encoding='utf-8')
    scan = source[source.index('  function enemyScanSection('):source.index('  function enemyPropertyLabel(')]
    battle = source[source.index('  function enemyBattleTextPanel('):source.index('  function enemyActionsPanel(')]
    page.add_script_tag(content='''
      const U=LexeditorUI,detailSection=U.detailSection,detailField=U.detailField,infoHelp=U.infoHelp;
      const row={id:0,name:'Belhelmel',scanDescription:'Scan description.'};
      const state={data:{},vanilla:{},references:[]},shell={refresh(){}};
      const lines=Array.from({length:4},(_,id)=>({id,text:'Short battle line.'}));
      const enemyBattleTextRow=()=>({available:true,lines}),rowOf=()=>row,referenceValues=()=>[];
      const sourceControl=input=>input;
    ''' + scan + battle)
    page.evaluate('''() => {
      const main=document.querySelector('main');
      main.style.cssText='width:460px;height:650px;flex:none;overflow:auto';
      main.append(enemyBattleTextPanel(row));
    }''')
    page.wait_for_timeout(100)
    inputs = page.locator('textarea')
    assert inputs.count() == 5
    assert inputs.evaluate_all('nodes=>nodes.every(n=>n.getBoundingClientRect().height<50)')
    assert page.locator('main').evaluate('n=>n.scrollHeight<=n.clientHeight')
    first = inputs.first
    short = first.bounding_box()['height']
    first.fill('One\nTwo\nThree\nFour\nFive')
    assert first.bounding_box()['height'] > short * 2
    first.fill('A long description that wraps naturally. ' * 8)
    page.locator('main').evaluate("n=>n.style.width='300px'")
    assert first.evaluate('n=>n.scrollHeight<=n.clientHeight+1')
    first.fill('Short again.')
    assert first.bounding_box()['height'] < 50
    page.screenshot(path=str(tmp_path / 'enemy-text.png'))
