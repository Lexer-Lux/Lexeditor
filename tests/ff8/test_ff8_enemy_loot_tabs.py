"""Loot tabs route to the existing editors without losing edits on navigation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'shared'))
from test_shared_ui_feedback import ROOT, framework, page


def test_enemy_loot_tabs_preserve_each_family(page, tmp_path):
    framework(page)
    page.add_style_tag(path=str(ROOT / 'plugins/ff8/editor.css'))
    source = (ROOT / 'plugins/ff8/party.js').read_text(encoding='utf-8')
    panel = source[source.index('  function enemyLootPanel('):source.index('  function enemyDetail(')]
    editors = source[source.index('  function enemyPairSection('):source.index('  const enemyDefencePrevious')]
    page.add_script_tag(content='''
      const U=LexeditorUI,el=U.el,tabbedPanel=U.tabbedPanel,detailSection=U.detailSection,
        columnList=U.columnList,multiNumberRow=U.multiNumberRow,infoHelp=U.infoHelp;
      const state={activeSource:'mine',selected:{},data:{enemyTables:{choices:{cards:[],devour:[{id:0,name:'Heal'}]}}}};
      const row={id:0,name:'Test enemy',tables:{cards:[{slot:0,cardId:255}],devour:[{slot:0,devourId:0}],renzokuken:[]}};
      for(const kind of ['mug','draw','drops']) row.tables[kind]=Object.fromEntries(
        ['low','medium','high'].map(tier=>[tier,[{slot:0,valueId:0,quantity:1}]]));
      const shell={refresh(){}},rowOf=()=>null,choiceName=()=>'',enemyTableSource=control=>control;
      const numberControl=(value,min,max,step,change,attrs={})=>el('input',{type:'number',value,min,max,step,...attrs,oninput:e=>change(Number(e.target.value))});
      const selectControl=(value,choices,change)=>el('select',{onchange:e=>change(Number(e.target.value))},
        ...choices.map(c=>el('option',{value:c.id,selected:c.id===value},c.name)));
      const magicSearchControl=()=>el('button',{},'Magic'),itemSearchControl=()=>el('button',{},'Item');
      function renderEnemies(){document.querySelector('main').replaceChildren(enemyLootPanel(row))}
    ''' + editors + panel)
    page.evaluate('renderEnemies()')
    page.get_by_role('spinbutton', name='MUG low choice 1 quantity', exact=True).fill('12')
    for label in ['Draw', 'Drops', 'Cards', 'Devour', 'Mug']:
        page.get_by_role('tab', name=label, exact=True).click()
        assert page.locator('.enemy-table-section').count() == 1
        assert page.locator('.enemy-table-section').inner_text().startswith(label.upper())
        page.evaluate('renderEnemies()')
        assert page.get_by_role('tab', name=label, exact=True).get_attribute('aria-selected') == 'true'
    assert page.get_by_role('spinbutton', name='MUG low choice 1 quantity', exact=True).input_value() == '12'
    assert page.evaluate('row.tables.mug.low[0].quantity') == 12
    page.screenshot(path=str(tmp_path / 'enemy-loot-tabs.png'))
